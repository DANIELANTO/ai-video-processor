import os
import subprocess
import json
import redis
from uuid import UUID
from openai import OpenAI
import httpx
import math

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

# Sync Redis client — always use the internal Docker port (6379), not the host-mapped one (6380)
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))

# OpenAI client
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=httpx.Client()
)

# Storage adapter
storage_adapter = AzureBlobStorageAdapter(
    connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
    container_name=os.getenv("AZURE_CONTAINER_NAME"),
    account_name=os.getenv("AZURE_ACCOUNT_NAME"),
    account_key=os.getenv("AZURE_ACCOUNT_KEY")
)

# Format message
def _format_ms_to_srt_time(ms: int) -> str:
    """Converts milliseconds to HH:MM:SS,mmm format required by SRT."""
    seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

# Get video duration in milliseconds
def get_video_duration_seconds(path: str) -> float:
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'json', path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    # Convert seconds (float) to milliseconds (int)
    return float(data['format']['duration'])

@celery_app.task(name="app.infrastructure.workers.transcribe_audio")
def transcribe_audio(job_id_str: str):
    job_id = UUID(job_id_str)
    db = _db_module.SessionLocal()
    repository = PostgresMediaJobRepository(db)
    
    try:
        job = repository.get_by_id(job_id)
        if not job or not job.storage_blob_id:
            return f"Error: Job {job_id} invalid or without associated file."

        # Notify start of transcription
        redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
            "status": "TRANSCRIBING",
            "progress": 0
        }))

        # Temporary paths in the container
        tmp_video_path = f"/tmp/{job_id}.mp4"
        tmp_audio_path = f"/tmp/{job_id}.mp3"

        # 1. Download video from Azure
        storage_adapter.download_file(job.storage_blob_id, tmp_video_path)

        # 2. Extract audio with FFmpeg
        subprocess.run(
            ['ffmpeg', '-y', '-i', tmp_video_path, '-q:a', '0', '-map', 'a', tmp_audio_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # 3. Call OpenAI Whisper asking for detailed JSON
        with open(tmp_audio_path, "rb") as audio_file:
            response = openai_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="verbose_json",
                timestamp_granularities=["segment"]
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
        job.subtitles = subtitles
        job.advance_status(JobStatus.REVIEW_PENDING)
        repository.save(job)
        redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
            "status": "REVIEW_PENDING",
            "progress": 100,
            "message": "Transcription completed. Ready for review."
        }))

        return f"Transcription successful for {job_id}. {len(subtitles)} segments generated."

    except Exception as e:
        # Handle failures: if something breaks, mark the job as FAILED
        if 'job' in locals() and job is not None:
            job.advance_status(JobStatus.FAILED)
            job.error_message = str(e)
            repository.save(job)
        raise e

    finally:
        # 6. Clean up to avoid saturating the container's disk
        if os.path.exists(tmp_video_path):
            os.remove(tmp_video_path)
        if os.path.exists(tmp_audio_path):
            os.remove(tmp_audio_path)
        db.close()

@celery_app.task(name="app.infrastructure.workers.render_video")
def render_video(job_id_str: str):
    job_id = UUID(job_id_str)
    db = _db_module.SessionLocal()
    repository = PostgresMediaJobRepository(db)
    
    try:
        job = repository.get_by_id(job_id)
        
        tmp_input_video = f"/tmp/{job_id}_in.mp4"
        tmp_srt_path = f"/tmp/{job_id}.srt"
        tmp_output_video = f"/tmp/{job_id}_out.mp4"

        # 1. Notify start
        redis_client.publish(f"channel:job:{job_id_str}", json.dumps({"status": "RENDERING", "progress": 0}))

        # 2. Download original video
        storage_adapter.download_file(job.storage_blob_id, tmp_input_video)

        # 3. Generate physical .srt file from our domain entities
        with open(tmp_srt_path, "w", encoding="utf-8") as f:
            for sub in job.subtitles:
                f.write(f"{sub.index}\n")
                f.write(f"{_format_ms_to_srt_time(sub.start_time_ms)} --> {_format_ms_to_srt_time(sub.end_time_ms)}\n")
                f.write(f"{sub.text}\n\n")

        # 4. Build and execute FFmpeg command
        estimated_duration = get_video_duration_seconds(tmp_input_video)
        
        # Filter: equalization + subtitles
        vf_filter = f"eq=brightness={job.rendering_params.brightness_increase},subtitles={tmp_srt_path}"
        
        cmd = [
            'ffmpeg', '-y', '-i', tmp_input_video, 
            '-vf', vf_filter, 
            '-c:a', 'copy',
            '-progress', '-', '-nostats', 
            tmp_output_video
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
        
        # 5. Read real-time progress and publish it to Redis
        for line in process.stdout:
            if "out_time_ms=" in line:
                current_time_seconds = int(line.split("=")[1].strip()) / 1000000
                # Avoid division by zero or percentages greater than 100
                percent = min(99, math.floor((current_time_seconds / max(0.1, estimated_duration)) * 100))
                if percent > 0:
                    redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
                        "status": "RENDERING", 
                        "progress": percent
                    }))

        process.wait()
        
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed with code {process.returncode}")

        # 6. Upload final file
        final_blob_name = f"final_{job.storage_blob_id}"
        final_url = storage_adapter.upload_file(tmp_output_video, final_blob_name)

        # 7. Complete job
        job.advance_status(JobStatus.COMPLETED)
        repository.save(job)
        
        redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
            "status": "COMPLETED", 
            "progress": 100,
            "final_url": final_url
        }))

    except Exception as e:
        if 'job' in locals() and job:
            job.advance_status(JobStatus.FAILED)
            job.error_message = str(e)
            repository.save(job)
            redis_client.publish(f"channel:job:{job_id_str}", json.dumps({"status": "FAILED", "error": str(e)}))
        raise e
    finally:
        # Clean up temporary files
        for path in [tmp_input_video, tmp_srt_path, tmp_output_video]:
            if os.path.exists(path):
                os.remove(path)
        db.close()