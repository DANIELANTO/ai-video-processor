# Architecture Design — AI Video Processor

> **For AI Agents:** Read this file before modifying any backend structure, adding layers, or introducing new dependencies.  
> Last updated: 2026-06-11

---

## 1. Architecture Overview

The project implements **Domain-Driven Design (DDD)** combined with **Clean Architecture** (also known as Hexagonal / Ports-and-Adapters Architecture).

The fundamental rule is: **dependency direction always flows inward, toward the domain**. The domain knows nothing about the database, HTTP, or external APIs. The infrastructure knows about the domain, but the domain never imports from the infrastructure.

```
┌────────────────────────────────────────────────────────────┐
│                     Presentation Layer                     │
│        (FastAPI routes, DTOs, Dependency Injection)        │
└────────────────────────┬───────────────────────────────────┘
                         │ calls
┌────────────────────────▼───────────────────────────────────┐
│                    Application Layer                       │
│           (Use Cases, Interface Definitions/Ports)         │
└──────────┬──────────────────────────────────┬──────────────┘
           │ depends on (inward)              │ defines (ports)
┌──────────▼──────────┐         ┌─────────────▼──────────────┐
│    Domain Layer     │         │   Infrastructure Layer      │
│  (Entities, Enums,  │         │  (Adapters: DB, Storage,    │
│   Business Rules)   │         │   Queue, Workers, PubSub)   │
└─────────────────────┘         └────────────────────────────┘
```

---

## 2. Layer Breakdown

### 2.1 Domain Layer — `app/domain/`

**Responsibility:** Defines the core business model and rules. Completely framework-agnostic.

**Files:**
- `entities.py` — All domain entities and value objects:
  - `JobStatus` (Enum): `PENDING → TRANSCRIBING → REVIEW_PENDING → RENDERING → COMPLETED | FAILED`
  - `SubtitleSegment` (Pydantic BaseModel): Represents one subtitle block. Validates that `start_time_ms < end_time_ms`.
  - `RenderingParameters` (Pydantic BaseModel): Rendering options (brightness). Defaults to `0.05`.
  - `MediaJob` (Pydantic BaseModel): The aggregate root. Contains the full lifecycle of a video processing job.

**Rules for this layer:**
- NO imports from `infrastructure`, `presentation`, or external frameworks (except Pydantic and stdlib).
- Business rules (e.g., time validation, state transitions) belong HERE.
- Adding new domain concepts (entities, value objects, enums) goes here.

---

### 2.2 Application Layer — `app/application/`

**Responsibility:** Orchestrates workflows through use cases. Defines ports (interfaces) that infrastructure must implement.

**Key files:**
- `interfaces.py` — Defines abstract base classes (ports/contracts):
  - `IMediaJobRepository`: `save(job)`, `get_by_id(job_id)`
  - `IFileStorage`: `generate_upload_url(filename)`, `download_file(...)`, `upload_file(...)`
  - `IQueueService`: `enqueue_transcription_task(job_id)`, `enqueue_rendering_task(job_id)`
  - `IEventStreamService`: `subscribe_to_job_events(job_id)` → async generator
- `use_cases/process_video.py` — Concrete use case classes:
  - `ProcessUploadedVideoUseCase`: Creates a job, gets a SAS token, saves to DB.
  - `ConfirmVideoUploadUseCase`: Advances status to `TRANSCRIBING`, enqueues transcription.
  - `SubmitFinalVideoRenderingUseCase`: Saves corrected subtitles, advances to `RENDERING`, enqueues render.

**Note:** There is also an `interfaces/` directory that appears unused. The canonical interfaces file is `interfaces.py` (flat file). See `decisions.md` for context.

**Rules for this layer:**
- Use cases must only receive **interfaces** as constructor arguments, never concrete adapters directly.
- No HTTP, no DB, no cloud SDK imports here.
- Each use case has a single `execute()` method.

---

### 2.3 Infrastructure Layer — `app/infrastructure/`

**Responsibility:** Implements the contracts defined in the application layer using real external services.

**Files:**
- `database.py` — SQLAlchemy engine, session factory (`SessionLocal`), `Base`, and the ORM model `MediaJobModel`.
- `repositories.py` — `PostgresMediaJobRepository(IMediaJobRepository)`: Handles CRUD for `MediaJobModel`, mapping between ORM model and domain entity.
- `storage.py` — `AzureBlobStorageAdapter(IFileStorage)`: Generates SAS tokens, downloads/uploads blobs.
- `celery_app.py` — Celery configuration: uses Redis as broker and result backend. Task serializer: JSON.
- `queue.py` — `CeleryQueueAdapter(IQueueService)`: Sends task IDs to the Celery queue via `delay()`.
- `pubsub.py` — `RedisEventStreamAdapter(IEventStreamService)`: Async Redis Pub/Sub subscriber that yields events as an async generator.
- `workers.py` — Celery task definitions:
  - `transcribe_audio(job_id_str)`: Downloads video, extracts audio (FFmpeg), calls Whisper API, saves subtitles, publishes progress to Redis.
  - `render_video(job_id_str)`: Downloads video, generates `.srt`, burns subtitles with FFmpeg, uploads result, publishes progress.

**Rules for this layer:**
- All classes here must implement an interface from `app/application/interfaces.py`.
- Workers directly use infrastructure dependencies (storage, Redis, DB) since they are not injected via FastAPI `Depends`.
- Temporary files are created in `/tmp/` and always cleaned up in `finally` blocks.

---

### 2.4 Presentation Layer — `app/presentation/`

**Responsibility:** HTTP interface. Handles routing, input validation (DTOs), dependency injection, and response formatting.

**Files:**
- `main.py` — The single FastAPI application file. Contains:
  - CORS middleware configuration (allows `localhost:5173`).
  - Dependency provider functions (`get_db`, `get_storage_adapter`, `get_queue_service`, `get_stream_service`).
  - Pydantic request DTOs: `UploadVideoRequest`, `RenderVideoRequest`.
  - All API endpoints (see Section 3).

**Rules for this layer:**
- Dependency injection wires concrete adapters to abstract interfaces.
- No business logic. Use cases handle all logic.
- HTTP error handling uses `HTTPException`.

---

## 3. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/jobs/upload` | Create job, return Azure SAS upload URL |
| `POST` | `/api/v1/jobs/{job_id}/confirm-upload` | Confirm upload done, enqueue transcription |
| `GET` | `/api/v1/jobs/{job_id}/stream` | SSE stream for real-time job status updates |
| `GET` | `/api/v1/jobs/{job_id}` | Get full job details (subtitles, status, final URL) |
| `POST` | `/api/v1/jobs/{job_id}/render` | Submit corrected subtitles and trigger rendering |

---

## 4. Data Flow — End-to-End

```
Browser ──POST /upload──► FastAPI ──► ProcessUploadedVideoUseCase
                                           │
                                    save(MediaJob) ──► PostgreSQL
                                           │
                            return: { job_id, upload_url (SAS) }
                                           │
Browser ──PUT file──────────────────────────────────────► Azure Blob Storage
                                                                    │
Browser ──POST /confirm-upload──► FastAPI ──► ConfirmVideoUploadUseCase
                                                    │
                                            enqueue(job_id) ──► Celery/Redis Queue
                                                                         │
                                                                  [Worker picks up]
                                                                         │
                                                          download ──► Azure ──► /tmp
                                                          FFmpeg extract audio
                                                          Whisper API ──► subtitles
                                                          save subtitles ──► PostgreSQL
                                                          publish events ──► Redis PubSub
                                                                         │
Browser ──GET /stream──► FastAPI ──► RedisEventStreamAdapter ──► SSE ──► Browser
                                                          (progress %, status)
                                                                         │
Browser ──GET /jobs/{id}──► FastAPI ──► repository.get_by_id() ──► subtitles
                                                                         │
Browser [edit subtitles] ──POST /render──► SubmitFinalVideoRenderingUseCase
                                                    │
                                            enqueue render ──► Celery Queue
                                                                         │
                                                            [Worker picks up]
                                                            download ──► Azure
                                                            build .srt file
                                                            FFmpeg burn subtitles
                                                            upload final ──► Azure
                                                            publish COMPLETED ──► Redis
                                                                         │
Browser [SSE] ──receives COMPLETED + final_url──► shows download link
```

---

## 5. Key Design Patterns

| Pattern | Where Applied |
|---|---|
| Clean Architecture | Overall backend structure |
| Domain-Driven Design | `app/domain/entities.py` (aggregate root, value objects, enums) |
| Ports & Adapters (Hexagonal) | `interfaces.py` defines ports; `infrastructure/` implements adapters |
| Dependency Injection | FastAPI `Depends` in `main.py` for all use case dependencies |
| Repository Pattern | `PostgresMediaJobRepository` abstracts all DB access |
| Event-Driven (Pub/Sub) | Redis Pub/Sub for real-time worker → browser communication |
| SSE (Server-Sent Events) | Async generator + `StreamingResponse` for push-based UI updates |
| Aggregate Root | `MediaJob` is the aggregate root; all state transitions go through it |

---

## 6. Database Schema

**Table:** `media_jobs`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Job identifier |
| `original_filename` | String | User-provided filename |
| `storage_blob_id` | String (nullable) | Azure blob name: `{uuid}_{safe_filename}` |
| `status` | String | Maps to `JobStatus` enum |
| `subtitles` | JSONB | List of `SubtitleSegment` dicts |
| `brightness_increase` | Float | Rendering parameter, default `0.05` |
| `created_at` | DateTime | Creation timestamp |
| `error_message` | String (nullable) | Set on `FAILED` status |

**Note:** The `final_url` is NOT stored in the DB. It is regenerated from the blob name on every `GET /jobs/{id}` request (using a fresh SAS token, valid 7 days). This is an intentional trade-off.

---

## 7. Risks & Points of Care

| Risk | Description |
|---|---|
| No database migrations | `Base.metadata.create_all()` is used. Adding columns requires manual intervention or Alembic setup. |
| Worker couples directly to infrastructure | Workers instantiate storage and DB adapters at module load time (not injected). This makes them harder to test. |
| CORS is hardcoded | Only `localhost:5173` is allowed. Production deployment requires updating this list. |
| No authentication | All API endpoints are publicly accessible. Any caller can create/read jobs. |
| Redis port discrepancy | Workers use `redis://redis:6380/0` in `workers.py` while `celery_app.py` defaults to `redis://redis:6379/0`. Redis is mapped as `6380:6379` externally but internally services talk at `6379`. Verify consistency. |
| No job listing | Only one job at a time is tracked in `localStorage`. No multi-job management. |
| Blocking Celery tasks | Celery workers use synchronous code (blocking I/O). This is appropriate but means one video per worker at a time. |
| `interfaces/` directory vs `interfaces.py` | An unused `interfaces/` directory exists alongside `interfaces.py`. This could cause confusion. |

---

## 8. Architecture Update Policy

This file must be updated whenever:
- A new layer or module is introduced.
- The dependency injection wiring changes.
- A new external service is integrated.
- A new endpoint is added or removed.
- The database schema is modified.
- A significant architectural decision is recorded in `decisions.md`.
- A spec implementation alters the data flow.
