# Technical Decisions Log — AI Video Processor

> **For AI Agents:** Read this file to understand WHY the project is structured as it is. Add new entries whenever a significant technical decision is made.  
> Last updated: 2026-06-11 (DEC-0011 added)

---

## Update Policy

This file **must** be updated whenever:
- The architecture changes.
- A new important dependency is added.
- A main convention changes.
- A critical decision is made that other agents must know about.
- The way files or modules are organized changes.
- The main execution flow of the system changes.

Use the format below. Do not delete old decisions — mark them as `Reemplazada` or `Deprecada` instead.

---

## DEC-0001: Domain-Driven Design with Clean Architecture

**Date:** 2026-06-11 (inferred from codebase)  
**Status:** Aceptada

**Contexto:**  
The project processes videos through multiple asynchronous stages involving external APIs, cloud storage, message queues, and a relational database. Without a clear structural approach, this complexity would lead to tightly coupled, hard-to-maintain code.

**Decisión:**  
Implement Clean Architecture organized into four strict layers: Domain, Application, Infrastructure, and Presentation. Enforce the dependency rule: outer layers depend on inner layers, never the reverse.

**Razón:**  
- Makes the core business logic (video job lifecycle, subtitle management) testable without mocking infrastructure.
- Allows swapping infrastructure implementations (e.g., replacing Azure with S3, or replacing Redis with RabbitMQ) without touching business logic.
- Scales well as the project grows in complexity.

**Impacto:**  
- All new features must follow the DDD layer order (domain → application → infrastructure → presentation).
- Violating the dependency rule (e.g., importing infrastructure from domain) is a breaking anti-pattern.

---

## DEC-0002: Asynchronous Processing via Celery + Redis

**Date:** 2026-06-11 (inferred from codebase)  
**Status:** Aceptada

**Contexto:**  
Video transcription (Whisper API) and rendering (FFmpeg) are heavy, long-running operations that can take minutes. Blocking an HTTP request for this duration is unacceptable.

**Decisión:**  
Use Celery with Redis as the message broker and result backend. Long-running tasks are enqueued and executed by dedicated worker containers, completely decoupled from the FastAPI API server.

**Razón:**  
- HTTP requests return immediately; the client is not blocked.
- Workers can be scaled independently of the API.
- Redis serves double duty as broker + Pub/Sub for SSE.

**Impacto:**  
- All heavy operations must be Celery tasks in `app/infrastructure/workers.py`.
- The API server and worker share the same `app/` codebase (mounted as volumes in Docker).
- Task names must be explicit strings (e.g., `"app.infrastructure.workers.transcribe_audio"`) to avoid auto-discovery issues.

---

## DEC-0003: Real-Time Progress via Redis Pub/Sub + Server-Sent Events (SSE)

**Date:** 2026-06-11 (inferred from codebase)  
**Status:** Aceptada

**Contexto:**  
The client needs real-time feedback on job progress (transcription %, rendering %) without polling.

**Decisión:**  
Workers publish JSON progress events to a Redis channel (`channel:job:{job_id}`). The FastAPI SSE endpoint subscribes to that channel via `RedisEventStreamAdapter` and streams events to the browser using `StreamingResponse` with `media_type="text/event-stream"`.

**Razón:**  
- SSE is simpler than WebSockets for unidirectional push (server → client).
- Redis Pub/Sub decouples the worker from the HTTP layer cleanly.
- Fits the Clean Architecture pattern: the SSE adapter implements `IEventStreamService`.

**Impacto:**  
- New background tasks that need real-time progress must publish to the same Redis channel pattern.
- The frontend `useJobStream` hook manages the `EventSource` connection lifecycle.
- The SSE stream does not auto-reconnect on worker errors — the frontend must handle disconnections.

---

## DEC-0004: Direct-to-Azure Upload (SAS Token Pattern)

**Date:** 2026-06-11 (inferred from codebase)  
**Status:** Aceptada

**Contexto:**  
Uploading large video files through the FastAPI server would create a bottleneck, consume server memory, and increase latency.

**Decisión:**  
The client requests a time-limited Azure SAS (Shared Access Signature) write token from the API, then uploads the file directly to Azure Blob Storage. The API only handles metadata (job creation and status confirmation).

**Razón:**  
- The FastAPI server is never in the data path for file uploads.
- Reduces server memory usage and I/O load.
- SAS tokens expire (1 hour) and grant only write permission to a specific blob, limiting security exposure.

**Impacto:**  
- The upload flow is always 3 steps: `POST /upload` → client PUT to Azure → `POST /confirm-upload`.
- The blob naming convention is: `{job_uuid}_{safe_filename}` where spaces are replaced by underscores.
- The final rendered file is named: `final_{original_blob_id}`.

---

## DEC-0005: JSONB for Subtitle Storage in PostgreSQL

**Date:** 2026-06-11 (inferred from codebase)  
**Status:** Aceptada

**Contexto:**  
Subtitles are a variable-length list of structured objects (`SubtitleSegment`). Normalizing them into a separate relational table adds join complexity without clear query benefit at this stage.

**Decisión:**  
Store subtitles as a JSONB column in `media_jobs`. Serialize/deserialize using `model_dump()` and `SubtitleSegment(**sub)` in the repository.

**Razón:**  
- Simpler schema for an MVP.
- JSONB allows querying and indexing on JSON fields if needed in the future.
- Subtitle data is always read/written as a complete list, never queried individually.

**Impacto:**  
- The repository must handle serialization manually in `save()` and `get_by_id()`.
- Adding new fields to `SubtitleSegment` requires backward compatibility checks for existing JSONB rows.

---

## DEC-0006: No Database Migrations (create_all approach)

**Date:** 2026-06-11 (inferred from codebase)  
**Status:** Aceptada (con deuda técnica)

**Contexto:**  
The project is in early development. Setting up Alembic adds initial overhead.

**Decisión:**  
Use `Base.metadata.create_all(bind=engine)` at API startup to create tables if they don't exist.

**Razón:**  
Acceptable for early MVP development.

**Impacto:**  
- Schema changes require manual SQL (`ALTER TABLE`) or full table recreation in development.
- **This must be replaced with Alembic before any production deployment.**
- When Alembic is introduced, create a DEC entry replacing this one.

---

## DEC-0007: Single Celery Worker Queue

**Date:** 2026-06-11 (inferred from codebase)  
**Status:** Aceptada

**Contexto:**  
The current system has two types of tasks: transcription (Whisper API-bound) and rendering (FFmpeg CPU-bound). They are handled by a single worker named `worker_whisper`.

**Decisión:**  
Use a single default Celery queue (`celery`) for both task types. One worker handles all tasks.

**Razón:**  
Simplifies the initial setup. Acceptable for MVP scale.

**Impacto:**  
- A rendering task will block transcription tasks and vice versa if the single worker is busy.
- To scale, separate queues (`transcription`, `rendering`) with dedicated workers should be introduced.
- A future spec should address queue separation.

---

## DEC-0008: `final_url` Regenerated at Read Time (Not Persisted)

**Date:** 2026-06-11 (inferred from codebase)  
**Status:** Aceptada

**Contexto:**  
Azure SAS URLs expire. Storing a generated URL in the DB would make it stale after expiry.

**Decisión:**  
The `final_url` is not stored in the `media_jobs` table. On every `GET /api/v1/jobs/{job_id}`, the API regenerates a fresh SAS read token from the blob name (`final_{storage_blob_id}`).

**Razón:**  
- Always-fresh, non-expiring access as long as the job exists.
- Simpler than implementing URL refresh logic.

**Impacto:**  
- The `MediaJob` domain entity has a `final_url` field, but it is always `None` from the DB. The presentation layer sets it before returning the response.
- If the blob is deleted from Azure, the `GET` endpoint will still return a URL (which will 404 when accessed).

---

## DEC-0009: Frontend Job State Persisted in localStorage

**Date:** 2026-06-11 (inferred from codebase)  
**Status:** Aceptada

**Contexto:**  
There is no user authentication. The frontend needs to remember the active job across page refreshes.

**Decisión:**  
The active `job_id` is saved in `localStorage` under the key `activeVideoJobId`. On load, `App.tsx` reads this to restore state.

**Razón:**  
Simple, zero-dependency persistence for MVP. Adequate without auth.

**Impacto:**  
- Only one job is tracked at a time (single-job UX).
- Clearing localStorage or opening a different browser loses the job reference.
- A future multi-job feature would require a job listing API and replace this pattern.

---

## DEC-0010: interfaces.py File vs interfaces/ Directory Ambiguity

**Date:** 2026-06-11  
**Status:** Pendiente de confirmar

**Contexto:**  
Both `app/application/interfaces.py` (a file) and `app/application/interfaces/` (a directory) exist. The file contains all interface definitions. The directory appears to be empty or unused.

**Decisión:**  
The canonical location for interfaces is `app/application/interfaces.py`. The directory is not used.

**Razón:**  
All imports in the codebase reference `app.application.interfaces` which resolves to the file.

**Impacto:**  
- The `interfaces/` directory should be removed to avoid confusion.
- Until removed, agents must not add code to the `interfaces/` directory.
- **Action needed:** Confirm with the project owner and remove the empty directory if confirmed unused.

---

## DEC-0011: Lazy Database Initialization via FastAPI Lifespan

**Date:** 2026-06-11  
**Status:** Aceptada

**Contexto:**  
Calling `create_engine()` and `Base.metadata.create_all()` at module import time caused a race condition: when Python first imported `database.py`, Docker's internal DNS resolver had not yet registered the `db` container hostname. This caused a fatal `OperationalError` (`could not translate host name "db"`) that killed the API container on startup — even with `depends_on: condition: service_healthy` in Docker Compose, because that healthcheck only guarantees Postgres is running, not that the network DNS has propagated by the time Python imports execute.

**Decisión:**  
- `database.py` now exports `engine = None` and `SessionLocal = None` at module level.
- A new `init_db()` function performs the actual `create_engine()` + retry loop.
- `main.py` calls `init_db()` and `Base.metadata.create_all()` inside a FastAPI `@asynccontextmanager` lifespan handler, which runs **after** Uvicorn has started and Docker networking is fully initialized.

**Razón:**  
- Lifespan handlers run significantly later than module imports, by which time Docker DNS is always ready.
- Preserves the existing retry logic (`_create_engine_with_retry`) without changes.
- Follows FastAPI's recommended pattern for startup/shutdown lifecycle management.

**Impacto:**  
- `SessionLocal` is `None` until `init_db()` runs. Any code calling `SessionLocal()` before `init_db()` will raise `TypeError: 'NoneType' object is not callable`.
- **Celery workers run in a separate process** and never execute the FastAPI lifespan. Therefore `workers.py` must call `init_db()` explicitly at module level. This is safe because `worker_whisper` depends on `db: condition: service_healthy`.
- All future startup-time initialization (e.g., cache warmup, connection pool setup) should be added to the lifespan handler in `main.py` (for the API process) and called explicitly in `workers.py` (for the worker process).

---

## DEC-0012: API Host Port Changed to 8001

**Date:** 2026-06-11  
**Status:** Aceptada

**Contexto:**  
Durante el bringup del stack, el puerto 8000 del host ya estaba ocupado por el contenedor `nodepay-ai-service-1`, perteneciente a otro proyecto del mismo entorno de desarrollo.

**Decisión:**  
Mapear el puerto host de la API a `8001` (`8001:8000` en `docker-compose.yml`). El puerto interno del contenedor permanece en `8000` (Uvicorn sigue corriendo en `0.0.0.0:8000` dentro del contenedor).

**Razón:**  
- La alternativa de detener `nodepay-ai-service` interrumpe otro proyecto activo.
- El cambio de puerto es local al entorno de Daniel; el puerto interno no cambia, por lo que la comunicación inter-contenedor (worker → API) no se ve afectada.

**Impacto:**  
- `frontend/.env`: `VITE_API_BASE_URL=http://localhost:8001/api/v1`
- `frontend/src/services/api.ts` y `useJobStream.ts`: fallback hardcodeado actualizado a `localhost:8001`.
- Swagger UI accesible en `http://localhost:8001/docs`.
- Si en el futuro el puerto 8000 queda libre, revertir a `8000:8000` en `docker-compose.yml` y actualizar los tres archivos de frontend.

---

## DEC-0013: Local Object URL for Video Preview

**Date:** 2026-06-11  
**Status:** Aceptada

**Contexto:**  
During the subtitle review phase, the user needs to preview the video to accurately correct the subtitles. Loading the video from Azure Blob Storage would incur egress costs, add latency, and require generating a read SAS token specifically for the frontend player.

**Decisión:**  
Create a local `blob:` Object URL from the original `File` object selected in the upload phase using `URL.createObjectURL(file)`. This URL is passed directly to the `<video>` element for local playback.

**Razón:**  
- Zero latency video playback.
- Zero egress cost from Azure.
- Avoids modifying backend API to support partial video streaming (Range requests) which is required for seeking in modern browsers.

**Impacto:**  
- If the user reloads the page during the `REVIEW_PENDING` state, the original `File` object is lost and the video preview will not be available. The UI must gracefully handle a missing `videoSrc` by showing a placeholder.
- The `App.tsx` component is responsible for creating and revoking the Object URL to prevent memory leaks.

---

## DEC-0014: FFmpeg Encoding Optimization (ultrafast preset)

**Date:** 2026-06-11
**Status:** Aceptada

**Contexto:**
El proceso de renderizado del video (`workers.py`) usando FFmpeg era muy lento debido a que se utilizaban los valores por defecto del encoder `libx264` (preset `medium`). Además, se presentaban crashes de tipo `ValueError` al leer valores `N/A` del log de progreso de FFmpeg.

**Decisión:**
Se configuró FFmpeg explícitamente para usar `-c:v libx264`, `-preset ultrafast`, `-crf 23` y `-threads 0`. También se añadió un bloque defensivo `try/except` para ignorar valores no numéricos (`N/A`) emitidos en el stream `out_time_ms`.

**Razón:**
- `ultrafast` reduce dramáticamente el tiempo de renderizado (hasta un 50-70% más rápido), aprovechando todos los hilos (`-threads 0`).
- El incremento en el tamaño de archivo es aceptable para la naturaleza MVP del proyecto.
- Evita que la tarea de Celery termine en `FAILED` prematuramente por errores de parseo de progreso.

**Impacto:**
- Mejor percepción de performance de renderizado.
- No es posible usar `-c:v copy` ya que el proceso aplica filtros de video (`-vf`) para subtítulos quemados y ecualización de brillo.

---

## DEC-0015: Azure Blob Upload — Explicit Timeouts, Block Upload, and Concurrency

**Date:** 2026-06-11
**Status:** Aceptada

**Contexto:**
`blob_client.upload_blob(data, overwrite=True)` with no configuration uses the Azure SDK's
default socket write timeout of ~20 seconds. A ~21.7 MB rendered MP4 uploaded from inside a
Docker container (which routes through the host network adapter) was consistently timing out,
triggering the SDK's internal retry loop (3 retries × 20s = 60+ seconds blocked) before failing
with `ServiceResponseError: ("Connection aborted.", TimeoutError("The write operation timed out"))`.

The 10+ minute job duration was caused by this retry cycle combined with no Celery task time limit,
leaving the worker blocked indefinitely.

**Decisión:**
Configure `BlobServiceClient.from_connection_string()` with:
- `connection_timeout=30` — TCP connect timeout.
- `read_timeout=300` — Socket write/read timeout per chunk (raised from ~20s default).
- `max_single_put_size=8 * 1024 * 1024` — Files > 8 MB use block (multi-part) upload.
- `max_block_size=4 * 1024 * 1024` — Each block is 4 MB.

Also pass `read_timeout=300` and `max_concurrency=4` directly to `upload_blob()`.

Additionally added to `celery_app.py`:
- `task_time_limit=600` — Hard kill after 10 minutes.
- `task_soft_time_limit=540` — Raises `SoftTimeLimitExceeded` at 9 minutes for graceful cleanup.

**Razón:**
- Block upload means a 21.7 MB file is split into ~6 blocks of 4 MB. If any block's connection
  drops, only that block retries — not the entire file.
- `read_timeout=300` gives each block 5 minutes to complete, handling legitimate network
  slowness without failing the entire job.
- `max_concurrency=4` sends up to 4 blocks in parallel, reducing total upload time.
- Task time limits prevent the worker from hanging indefinitely if all retries fail.

**Impacto:**
- `app/infrastructure/storage.py`: `BlobServiceClient` and `upload_blob()` now have explicit config.
- `app/infrastructure/celery_app.py`: Both tasks are now bounded to 10 minutes max.
- `app/infrastructure/workers.py`: Added `SoftTimeLimitExceeded` handler to both tasks so that
  temp files are cleaned up and the job is marked `FAILED` gracefully before the hard kill fires.
- All other upload/download/SAS behavior is unchanged.
- If the SDK version is upgraded beyond `azure-storage-blob==12.28.0`, verify that the
  `max_single_put_size`, `max_block_size`, `connection_timeout`, and `read_timeout` kwargs
  are still accepted by `BlobServiceClient.from_connection_string()`.
