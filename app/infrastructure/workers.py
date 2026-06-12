import os
import subprocess
import json
import logging
import math
import time
from uuid import UUID

import redis
from openai import OpenAI
import httpx
from celery.exceptions import SoftTimeLimitExceeded

from app.infrastructure.celery_app import celery_app
import app.infrastructure.database as _db_module
from app.infrastructure.repositories import PostgresMediaJobRepository
from app.infrastructure.storage import AzureBlobStorageAdapter
from app.domain.entities import JobStatus, SubtitleSegment

# Workers run in a separate process from FastAPI and never execute the lifespan
# handler, so SessionLocal would remain None. We must call init_db() explicitly
# here. The worker_whisper container depends on db: condition: service_healthy,
# so the DB is guaranteed to be reachable at this point. (See DEC-0011.)
_db_module.init_db()

# Module-level logger — Celery forwards this to the worker log stream.
logger = logging.getLogger(__name__)

# Sync Redis client — always use the internal Docker port (6379), not the host-mapped one (6380)
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))

# OpenAI client
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=httpx.Client()
)

# Storage adapter — configured with explicit timeouts and block-upload settings.
# (See spec: 2026-06-11-azure-upload-timeout-and-perf-overhaul.md)
storage_adapter = AzureBlobStorageAdapter(
    connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
    container_name=os.getenv("AZURE_CONTAINER_NAME"),
    account_name=os.getenv("AZURE_ACCOUNT_NAME"),
    account_key=os.getenv("AZURE_ACCOUNT_KEY")
)


def _format_ms_to_srt_time(ms: int) -> str:
    """Converts milliseconds to HH:MM:SS,mmm format required by SRT."""
    seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def get_video_duration_seconds(path: str) -> float:
    """Returns the video duration in seconds using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'json', path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data['format']['duration'])


@celery_app.task(name="app.infrastructure.workers.transcribe_audio")
def transcribe_audio(job_id_str: str):
    job_id = UUID(job_id_str)
    db = _db_module.SessionLocal()
    repository = PostgresMediaJobRepository(db)
    t_task_start = time.perf_counter()

    tmp_video_path = f"/tmp/{job_id}.mp4"
    tmp_audio_path = f"/tmp/{job_id}.mp3"

    try:
        job = repository.get_by_id(job_id)
        if not job or not job.storage_blob_id:
            return f"Error: Job {job_id} invalid or without associated file."

        logger.info("[transcribe_audio] START job=%s", job_id_str)

        # Notify start of transcription
        redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
            "status": "TRANSCRIBING",
            "progress": 0
        }))

        # 1. Download video from Azure
        t0 = time.perf_counter()
        storage_adapter.download_file(job.storage_blob_id, tmp_video_path)
        video_size = os.path.getsize(tmp_video_path)
        logger.info(
            "[transcribe_audio] stage=download job=%s duration=%.2fs size=%d bytes",
            job_id_str, time.perf_counter() - t0, video_size
        )

        # 2. Extract audio with FFmpeg
        t0 = time.perf_counter()
        subprocess.run(
            ['ffmpeg', '-y', '-i', tmp_video_path, '-q:a', '0', '-map', 'a', tmp_audio_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        audio_size = os.path.getsize(tmp_audio_path)
        logger.info(
            "[transcribe_audio] stage=audio_extract job=%s duration=%.2fs size=%d bytes",
            job_id_str, time.perf_counter() - t0, audio_size
        )

        # 3. Call OpenAI Whisper asking for detailed JSON
        t0 = time.perf_counter()
        with open(tmp_audio_path, "rb") as audio_file:
            response = openai_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        logger.info(
            "[transcribe_audio] stage=whisper_api job=%s duration=%.2fs segments=%d",
            job_id_str, time.perf_counter() - t0, len(response.segments)
        )

        # 4. Transform OpenAI segments to our Domain Entities
        subtitles = []
        for index, segment in enumerate(response.segments, start=1):
            subtitles.append(SubtitleSegment(
                index=index,
                start_time_ms=int(segment['start'] * 1000),
                end_time_ms=int(segment['end'] * 1000),
                text=segment['text'].strip()
            ))

        # 5. Save subtitles to the database (PostgreSQL JSONB) and advance status
        t0 = time.perf_counter()
        job.subtitles = subtitles
        job.advance_status(JobStatus.REVIEW_PENDING)
        repository.save(job)
        logger.info(
            "[transcribe_audio] stage=db_save job=%s duration=%.2fs",
            job_id_str, time.perf_counter() - t0
        )

        redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
            "status": "REVIEW_PENDING",
            "progress": 100,
            "message": "Transcription completed. Ready for review."
        }))

        logger.info(
            "[transcribe_audio] COMPLETED job=%s total=%.2fs segments=%d",
            job_id_str, time.perf_counter() - t_task_start, len(subtitles)
        )
        return f"Transcription successful for {job_id}. {len(subtitles)} segments generated."

    except SoftTimeLimitExceeded:
        # Graceful shutdown before the hard kill (task_time_limit) fires.
        # The finally block will still run to clean up temp files.
        logger.error("[transcribe_audio] SOFT TIME LIMIT EXCEEDED job=%s", job_id_str)
        if 'job' in locals() and job is not None:
            job.advance_status(JobStatus.FAILED)
            job.error_message = "Task exceeded time limit (9 minutes)."
            repository.save(job)
            redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
                "status": "FAILED",
                "error": "Task timeout: exceeded maximum allowed processing time."
            }))

    except Exception as e:
        logger.error("[transcribe_audio] FAILED job=%s error=%s", job_id_str, str(e), exc_info=True)
        if 'job' in locals() and job is not None:
            job.advance_status(JobStatus.FAILED)
            job.error_message = str(e)
            repository.save(job)
        raise e

    finally:
        # Clean up to avoid saturating the container's disk
        for path in [tmp_video_path, tmp_audio_path]:
            if os.path.exists(path):
                os.remove(path)
        db.close()


@celery_app.task(name="app.infrastructure.workers.render_video")
def render_video(job_id_str: str):
    job_id = UUID(job_id_str)
    db = _db_module.SessionLocal()
    repository = PostgresMediaJobRepository(db)
    t_task_start = time.perf_counter()

    tmp_input_video = f"/tmp/{job_id}_in.mp4"
    tmp_srt_path = f"/tmp/{job_id}.srt"
    tmp_output_video = f"/tmp/{job_id}_out.mp4"

    try:
        job = repository.get_by_id(job_id)

        logger.info("[render_video] START job=%s", job_id_str)

        # 1. Notify start
        redis_client.publish(f"channel:job:{job_id_str}", json.dumps({"status": "RENDERING", "progress": 0}))

        # 2. Download original video
        t0 = time.perf_counter()
        storage_adapter.download_file(job.storage_blob_id, tmp_input_video)
        input_size = os.path.getsize(tmp_input_video)
        logger.info(
            "[render_video] stage=download job=%s duration=%.2fs size=%d bytes",
            job_id_str, time.perf_counter() - t0, input_size
        )

        # 3. Generate physical .srt file from our domain entities
        with open(tmp_srt_path, "w", encoding="utf-8") as f:
            for sub in job.subtitles:
                f.write(f"{sub.index}\n")
                f.write(f"{_format_ms_to_srt_time(sub.start_time_ms)} --> {_format_ms_to_srt_time(sub.end_time_ms)}\n")
                f.write(f"{sub.text}\n\n")

        # 4. Build and execute FFmpeg command
        estimated_duration = get_video_duration_seconds(tmp_input_video)

        # Filter: brightness equalization + subtitle burn-in
        vf_filter = f"eq=brightness={job.rendering_params.brightness_increase},subtitles={tmp_srt_path}"

        cmd = [
            'ffmpeg', '-y', '-i', tmp_input_video,
            '-vf', vf_filter,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',     # Fast encoding; acceptable quality for MVP (See DEC-0014)
            '-crf', '23',               # Constant quality factor
            '-threads', '0',            # Use all available CPU cores
            '-c:a', 'copy',
            '-progress', '-', '-nostats',
            tmp_output_video
        ]

        t0 = time.perf_counter()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # 5. Read real-time progress and publish it to Redis.
        # Throttle: only publish when the percent value changes to avoid
        # flooding Redis with ~25 events/sec from FFmpeg's progress output.
        last_published = -1
        for line in process.stdout:
            if "out_time_ms=" in line:
                raw_value = line.split("=")[1].strip()
                try:
                    current_time_us = int(raw_value)
                except ValueError:
                    # FFmpeg emits 'N/A' at the start/end of processing — skip silently
                    continue
                if current_time_us <= 0:
                    continue

                current_time_seconds = current_time_us / 1_000_000
                # Avoid division by zero or percentages greater than 100
                percent = min(99, math.floor((current_time_seconds / max(0.1, estimated_duration)) * 100))
                if percent > 0 and percent != last_published:
                    redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
                        "status": "RENDERING",
                        "progress": percent
                    }))
                    last_published = percent

        process.wait()
        output_size = os.path.getsize(tmp_output_video) if os.path.exists(tmp_output_video) else 0
        logger.info(
            "[render_video] stage=ffmpeg job=%s duration=%.2fs input=%d bytes output=%d bytes",
            job_id_str, time.perf_counter() - t0, input_size, output_size
        )

        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed with code {process.returncode}")

        # 6. Upload final file to Azure Blob Storage
        final_blob_name = f"final_{job.storage_blob_id}"
        t0 = time.perf_counter()
        logger.info(
            "[render_video] stage=upload_start job=%s blob=%s size=%d bytes",
            job_id_str, final_blob_name, output_size
        )
        final_url = storage_adapter.upload_file(tmp_output_video, final_blob_name)
        logger.info(
            "[render_video] stage=upload_done job=%s duration=%.2fs",
            job_id_str, time.perf_counter() - t0
        )

        # 7. Complete job
        t0 = time.perf_counter()
        job.advance_status(JobStatus.COMPLETED)
        repository.save(job)
        logger.info(
            "[render_video] stage=db_save job=%s duration=%.2fs",
            job_id_str, time.perf_counter() - t0
        )

        redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
            "status": "COMPLETED",
            "progress": 100,
            "final_url": final_url
        }))

        logger.info(
            "[render_video] COMPLETED job=%s total=%.2fs output=%d bytes",
            job_id_str, time.perf_counter() - t_task_start, output_size
        )

    except SoftTimeLimitExceeded:
        # Graceful shutdown before the hard kill (task_time_limit) fires.
        # The finally block will still run to clean up temp files.
        logger.error("[render_video] SOFT TIME LIMIT EXCEEDED job=%s", job_id_str)
        if 'job' in locals() and job:
            job.advance_status(JobStatus.FAILED)
            job.error_message = "Task exceeded time limit (9 minutes)."
            repository.save(job)
            redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
                "status": "FAILED",
                "error": "Task timeout: exceeded maximum allowed processing time."
            }))

    except Exception as e:
        logger.error("[render_video] FAILED job=%s error=%s", job_id_str, str(e), exc_info=True)
        if 'job' in locals() and job:
            job.advance_status(JobStatus.FAILED)
            job.error_message = str(e)
            repository.save(job)
            redis_client.publish(f"channel:job:{job_id_str}", json.dumps({"status": "FAILED", "error": str(e)}))
        raise e

    finally:
        # Clean up temporary files — runs even on SoftTimeLimitExceeded
        for path in [tmp_input_video, tmp_srt_path, tmp_output_video]:
            if os.path.exists(path):
                os.remove(path)
        db.close()