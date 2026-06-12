# Spec: Azure Upload Timeout Fix + End-to-End Performance Overhaul

## Status

`Partially Implemented — Phases 1 and 2 completed (2026-06-11). Phases 3 and 4 pending.`

---

## Context

A 24-second video takes **more than 10 minutes** to complete the full pipeline. A
`ServiceResponseError: ("Connection aborted.", TimeoutError("The write operation timed out"))`
is thrown during `render_video` when calling `storage_adapter.upload_file(tmp_output_video, final_blob_name)`,
specifically inside `blob_client.upload_blob(data, overwrite=True)`.

Multiple PUT attempts are logged before the final timeout, indicating the Azure SDK is
retrying internally but ultimately failing. The rendered MP4 is ~21.7 MB.

Previous spec `2026-06-11-fix-render-video-na-crash-and-perf.md` fixed the N/A crash and
added `ultrafast` FFmpeg preset. **This spec picks up where that one left off** and
addresses the Azure upload timeout as the new critical blocker, plus remaining bottlenecks.

---

## Root Cause Diagnosis

### P0 — Azure Blob Upload Timeout (Critical Blocker)

**Root cause:** `blob_client.upload_blob(data, overwrite=True)` with no explicit
configuration uses the Azure SDK's **default socket write timeout of 20 seconds** for
each individual network write chunk. For a ~21.7 MB file uploaded from inside a Docker
container (which routes through the host's network adapter), a single burst of latency
or a network microinterruption exceeds this threshold and the write operation fails.

**Evidence:**
- Repeated PUT attempts → SDK's default retry policy fires (3 retries × 20s timeout = 60+ seconds blocked).
- "Connection aborted. TimeoutError: The write operation timed out."
- Only happens at upload stage, not at download (download already uses chunked streaming correctly).

**Fix:** Configure `BlobServiceClient` and `upload_blob()` with:
1. Explicit `connection_timeout=30` and `read_timeout=300` parameters.
2. Chunked block upload via `max_single_put_size=8*1024*1024` and `max_block_size=4*1024*1024`.
3. `max_concurrency=4` for parallel block uploading.

### P1 — No Time Limits on Celery Tasks

`celery_app.py` has no `task_time_limit` or `task_soft_time_limit`. If any task hangs
(network timeout, FFmpeg stall), the worker process blocks forever. This explains the
"more than 10 minutes" duration: the Celery task is not killed, it just waits for the
Azure SDK retry/timeout cycle to complete.

### P1 — Single-Stream Upload Without Block Upload

The current code opens the file as a plain Python file object and passes it directly to
`upload_blob()`. The Azure SDK uploads small files (<64 MB by default) as a single PUT.
A 21.7 MB file falls into this single-PUT path. If the connection drops mid-upload,
the entire upload restarts from zero. Block upload allows per-block retries.

### P2 — No Per-Stage Timing / Observability

There are no timing logs for individual pipeline stages. When something is slow, there
is no way to know whether it's the download, FFmpeg, or the upload without examining
Docker logs manually.

### P2 — AzureBlobStorageAdapter Has No Explicit Timeout or Retry Config

`storage.py` calls `BlobServiceClient.from_connection_string(connection_string)` with no
additional kwargs. The SDK uses its hardcoded defaults (connection timeout: 20s, read
timeout: 20s, 3 retries). These defaults are too aggressive (too short) for a Docker
network path.

### P3 — Worker Has No CPU/Memory Limits in docker-compose.yml

`worker_whisper` service has no `deploy.resources.limits` section. FFmpeg's `-threads 0`
can saturate all host cores, potentially triggering Docker Desktop CPU throttling.

### P3 — Redis Pub/Sub Publishes on Every FFmpeg Progress Line

The rendering loop publishes a Redis event on every progress line where `percent > 0`.
FFmpeg emits at ~25Hz → ~600 Redis PUBLISH calls for a 24-second video. Not the
primary bottleneck but wasteful and adds unnecessary noise to the Redis channel.

---

## Objective

1. Fix the Azure Blob upload timeout (`ServiceResponseError: write operation timed out`).
2. Add Celery task time limits to prevent infinite hangs.
3. Add per-stage instrumentation logging to all pipeline stages.
4. Throttle Redis publish rate during FFmpeg rendering.
5. Define the path for queue separation and resource governance (Phase 3–4).

---

## Scope

- `app/infrastructure/storage.py` — Azure SDK timeout + block upload configuration.
- `app/infrastructure/celery_app.py` — Task time limits.
- `app/infrastructure/workers.py` — Instrumentation, SoftTimeLimitExceeded handler, Redis throttle.
- `docker-compose.yml` — Resource limits (Phase 4); new worker service (Phase 3).
- `app/infrastructure/queue.py` — Queue routing (Phase 3).

## Out of Scope

- No changes to domain or application layers.
- No changes to database schema.
- No changes to frontend.
- No new external dependencies beyond what's already in `requirements.txt`.
- No changes to Whisper transcription model or provider.

---

## Affected Files

| File | Phase | Change Type |
|---|---|---|
| `app/infrastructure/storage.py` | 2 | Timeout and block upload configuration |
| `app/infrastructure/celery_app.py` | 2 | Add task time limits |
| `app/infrastructure/workers.py` | 1+2 | Instrumentation, SoftTimeLimitExceeded handler, throttle Redis |
| `docker-compose.yml` | 3–4 | Queue separation + worker_renderer, resource limits |
| `app/infrastructure/queue.py` | 3 | Route render to rendering queue |
| `.ai/context/decisions.md` | Post-impl | Add DEC-0015, update DEC-0007 |
| `.ai/context/architecture-design.md` | Post-impl | New worker service |
| `.ai/context/file-map.md` | Post-impl | New service entry |

---

## Implementation Plan

### Phase 1: Instrumentation and Measurement

Goal: See exactly where time is spent. Do not guess.

1. Add `import logging` and `import time` to `workers.py`.
2. Create module-level `logger = logging.getLogger(__name__)`.
3. Wrap each pipeline stage with `t0 = time.perf_counter()` / `logger.info(...)`.
4. Log: stage name, job_id, duration in seconds, file size in bytes.
5. Run a full job and capture Docker logs as baseline.

Acceptance:
- Every pipeline stage emits a timing log line.
- No functional behavior changes.

---

### Phase 2: Low-Risk Performance Fixes

Goal: Fix the Azure upload timeout and add safety time limits.

#### 2a — Fix `app/infrastructure/storage.py`

```python
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas

class AzureBlobStorageAdapter(IFileStorage):
    def __init__(self, connection_string, container_name, account_name, account_key):
        self.connection_string = connection_string
        self.container_name = container_name
        self.account_name = account_name
        self.account_key = account_key
        self.blob_service_client = BlobServiceClient.from_connection_string(
            connection_string,
            connection_timeout=30,          # TCP connection timeout (seconds)
            read_timeout=300,               # Socket read/write timeout (seconds)
            max_single_put_size=8 * 1024 * 1024,   # Files > 8 MB use block upload
            max_block_size=4 * 1024 * 1024,        # Each block = 4 MB
        )

    def upload_file(self, local_path: str, blob_name: str) -> str:
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        with open(local_path, "rb") as data:
            blob_client.upload_blob(
                data,
                overwrite=True,
                connection_timeout=30,
                read_timeout=300,
                max_concurrency=4,  # 4 parallel block upload connections
            )
        # SAS token generation — unchanged
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=7)
        )
        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"
```

#### 2b — Fix `app/infrastructure/celery_app.py`

```python
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_time_limit=600,          # Hard kill after 10 minutes
    task_soft_time_limit=540,     # Raise SoftTimeLimitExceeded after 9 minutes
)
```

#### 2c — Fix `app/infrastructure/workers.py`

Add to imports:
```python
import logging
import time
from celery.exceptions import SoftTimeLimitExceeded

logger = logging.getLogger(__name__)
```

Add `SoftTimeLimitExceeded` catch block to both `transcribe_audio` and `render_video`:
```python
except SoftTimeLimitExceeded:
    if 'job' in locals() and job:
        job.advance_status(JobStatus.FAILED)
        job.error_message = "Task exceeded time limit (9 minutes)."
        repository.save(job)
        redis_client.publish(f"channel:job:{job_id_str}",
                             json.dumps({"status": "FAILED", "error": "Task timeout"}))
```

Wrap each stage with timing:
```python
t0 = time.perf_counter()
storage_adapter.download_file(job.storage_blob_id, tmp_input_video)
logger.info("[render_video] stage=download job=%s duration=%.2fs size=%d bytes",
            job_id_str, time.perf_counter() - t0, os.path.getsize(tmp_input_video))
```

Throttle Redis publish in FFmpeg loop:
```python
last_published = -1
for line in process.stdout:
    if "out_time_ms=" in line:
        raw_value = line.split("=")[1].strip()
        try:
            current_time_us = int(raw_value)
        except ValueError:
            continue
        if current_time_us <= 0:
            continue
        current_time_seconds = current_time_us / 1000000
        percent = min(99, math.floor((current_time_seconds / max(0.1, estimated_duration)) * 100))
        if percent > 0 and percent != last_published:
            redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
                "status": "RENDERING",
                "progress": percent
            }))
            last_published = percent
```

---

### Phase 3: Architecture / Task Orchestration Improvements

Goal: Prevent task starvation between transcription and rendering.

1. Add `task_routes` to `celery_app.py` defining `transcription` and `rendering` queues.
2. Assign `@celery_app.task(..., queue='transcription')` and `(..., queue='rendering')`.
3. Update `queue.py` `CeleryQueueAdapter` to send to correct queue names.
4. Add `worker_renderer` service in `docker-compose.yml`.
5. Update `decisions.md`: mark DEC-0007 as `Superseded`, add DEC-0015.

---

### Phase 4: Scalability Improvements

Goal: Predictable resource usage under load.

1. Add `deploy.resources.limits` to both worker services in `docker-compose.yml`.
2. Add `worker_max_tasks_per_child=5` to Celery config.
3. Set explicit `--concurrency=1` on worker commands.

---

## Acceptance Criteria

| ID | Criterion |
|---|---|
| CA-01 | A 24-second (~21.7 MB output) video completes the full pipeline in < 3 minutes (target). |
| CA-02 | Azure upload does NOT timeout. Worker logs show `stage=upload` with successful duration. |
| CA-03 | If upload fails after all retries, job is marked `FAILED` with a descriptive error message. |
| CA-04 | If any task runs for 9 minutes, `SoftTimeLimitExceeded` fires and job is marked `FAILED`. |
| CA-05 | Worker logs show per-stage timing: download, ffmpeg, upload, with file sizes. |
| CA-06 | Redis progress publish rate is at most 1 event per percentage point (max 100 events per job). |
| CA-07 | All existing features remain: Whisper transcription, subtitle editing, FFmpeg rendering, brightness equalization, Azure upload, Celery async, SSE progress, download link. |
| CA-08 | No domain or application layer files are modified. |

---

## Risks

| Risk | Probability | Mitigation |
|---|---|---|
| `max_single_put_size` / `max_block_size` param names differ in SDK 12.28.0 | Low-Medium | Verify against SDK source; fallback: set at `upload_blob()` call level with `max_concurrency` |
| `SoftTimeLimitExceeded` requires signal support (POSIX only) | Low | Linux containers: fine. Not applicable to Windows-based containers. |
| Increasing `read_timeout=300` delays detection of truly dead connections | Low | Offset by retry policy and the 600s hard task time limit |
| Block upload increases Azure transaction costs (more API calls) | Very low | Cost delta is negligible for MVP scale |

---

## Notes for Future Agents

- The `AzureBlobStorageAdapter` is a singleton in `workers.py` (module-level). After
  implementing Phase 2, if the underlying SDK connection pool behaves incorrectly after
  a failed upload, consider instantiating a fresh `BlobServiceClient` per task.
- DEC-0007 must be formally superseded in Phase 3. Create DEC-0015 for the Azure
  upload configuration decision.
- The `--reload` flag in the Uvicorn CMD in `Dockerfile` is appropriate only for
  development. Remove it before any production deployment.
- The `download_file` method already uses chunked streaming correctly (`.chunks()`).
  No changes needed there.

---

## Implementation Notes

**Implementation date Phase 1+2:** 2026-06-11

**Changes made:**
- `app/infrastructure/storage.py`: Configured `BlobServiceClient` with `connection_timeout=30`,
  `read_timeout=300`, `max_single_put_size=8MB`, `max_block_size=4MB`. Added `read_timeout=300`
  and `max_concurrency=4` to `upload_blob()` call. Block upload now used for files > 8 MB.
- `app/infrastructure/celery_app.py`: Added `task_time_limit=600` and
  `task_soft_time_limit=540`.
- `app/infrastructure/workers.py`: Added `logging` + `time.perf_counter()` instrumentation
  to all pipeline stages in both tasks. Added `SoftTimeLimitExceeded` handler to both
  tasks for graceful timeout recovery. Added Redis publish throttling (once per
  percentage point, max 100 events per job). Standardized temp-path variable hoisting
  before `try` block in `transcribe_audio` to match `render_video` pattern.

**Context files updated:**
- [x] `.ai/context/decisions.md` (DEC-0015 added)
- [ ] `.ai/context/architecture-design.md` (pending Phase 3)
- [ ] `.ai/context/file-map.md` (pending Phase 3)
- [ ] `.ai/context/project-context.md`
