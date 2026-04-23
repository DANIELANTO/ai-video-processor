# AI Video Processor

A comprehensive end-to-end system designed for AI-driven video processing. It handles video uploads, automated transcription using OpenAI Whisper, subtitle review, and final video rendering with burned-in subtitles. 

The project applies robust software engineering principles, primarily **Domain-Driven Design (DDD)** and **Clean Architecture**, ensuring a decoupled, scalable, and highly maintainable codebase.

---

## 🏛 System Architecture & Paradigms

The backend is built with **FastAPI** leveraging a strict layering pattern to separate concerns. It actively practices **Dependency Injection** to decouple core business logic from specific infrastructure details (like databases and external APIs).

### Layered Architecture (DDD)
The `/app` directory is cleanly divided into 4 primary layers:

1. **Domain (`/app/domain`)**: Contains enterprise logic and entities (`MediaJob`, `SubtitleSegment`, `JobStatus`). These classes hold business rules and state, completely agnostic to databases or external libraries.
2. **Application (`/app/application`)**: Houses the **Use Cases** (`ProcessUploadedVideoUseCase`, `ConfirmVideoUploadUseCase`, etc.) and system **Interfaces** (`IEventStreamService`). This layer coordinates the workflow but leaves the concrete execution of external tasks to adapters.
3. **Infrastructure (`/app/infrastructure`)**: Implements the adapters for external services. Here resides the SQLAlchemy database connections, Postgres Repositories, Azure Blob Storage Adapters, Redis Pub/Sub, and Celery Workers. 
4. **Presentation (`/app/presentation`)**: The HTTP Interface built with FastAPI (`main.py`). It handles input validation (Pydantic), dependency injection of adapters into use cases, and routing.

### Key Principles Implemented
- **Clean Architecture / Hexagonal**: The core domain knows nothing of the outside world. Interfaces are defined eagerly and implemented lazily.
- **Dependency Injection**: FastAPI's `Depends` system enables swapping out infrastructures (e.g., local storage vs object storage, or mocking dependencies during tests) without modifying the use cases.
- **Asynchronous Processing**: Heavy AI/Video workloads are fully decoupled from HTTP requests. The API responds immediately, offloading the processing to background workers.
- **Event-Driven UI (SSE)**: State updates are pushed proactively to the client instead of making the client violently poll the backend.

---

## 🔗 How it is Connected (The Workflow)

The system features an asynchronous lifecycle connecting the browser, the API, the Database, background Workers, and third-party APIs.

### 1. Upload Phase (Direct-to-Cloud)
- **Frontend** requests an upload token from the Backend (`POST /api/v1/jobs/upload`).
- The API creates a `MediaJob` in **PostgreSQL** and generates an **Azure SAS (Shared Access Signature)** token.
- **Frontend** uploads the physical video file *directly* to **Azure Blob Storage**, bypassing the FastAPI server to reduce bottlenecks.
- Once finished, the frontend confirms the upload (`POST /api/v1/jobs/{job_id}/confirm-upload`), which queues the transcription task.

### 2. Transcription Phase (Celery + Redis + Whisper)
- The **Celery Worker** (`worker_whisper`) picks up the transcription job.
- **Worker** downloads the video from Azure and uses local **FFmpeg** to extract lightweight audio.
- The audio is sent to the **OpenAI Whisper API** for high-accuracy, timestamp-granular transcription.
- The worker saves the resulting `SubtitleSegment` list as JSONB inside the **PostgreSQL** database.
- *Real-time Progress:* Throughout this process, the worker publishes progress updates to a **Redis** pub/sub channel. The FastAPI `GET /api/v1/jobs/{job_id}/stream` endpoint listens to this channel and streams **Server-Sent Events (SSE)** directly to the browser.

### 3. Review Phase
- The UI transitions from "Processing" to a review editor, pulling the parsed subtitles via the `GET /api/v1/jobs/{job_id}` endpoint.
- The user can edit the text natively on the browser.

### 4. Final Render Phase (FFmpeg)
- The frontend sends the approved subtitles to the backend (`POST /api/v1/jobs/{job_id}/render`), which queues the rendering task.
- The **Worker** reconstructs an `.srt` file locally from the database payload.
- **FFmpeg** is invoked on the worker node to perform video equalization (brightness filters) and physically "burn" the subtitles onto the video track.
- Similar to transcription, processing metrics outputted by FFmpeg are captured in real-time, scaled by the video's mathematical duration, and streamed back to the frontend via Redis + SSE.
- The finalized video is uploaded back to **Azure**, and the frontend is provided with the final downloadable link.

---

## 🛠 Tech Stack

### Backend
- **Python 3.x**
- **FastAPI**: Asynchronous web framework.
- **SQLAlchemy & PostgreSQL**: RDBMS for persistence; using JSONB to store dynamic subtitle blobs efficiently.
- **Celery**: Distributed task queue for managing background processes.
- **Redis**: Multi-purpose usage as a Celery Message Broker / Result Backend AND as a Pub/Sub layer for live event streaming.
- **FFmpeg**: Handled via `subprocess` for system-level media processing.
- **OpenAI API**: Utilizing `whisper-1` for AI transcription.
- **Azure Blob Storage**: Cloud object storage.

### Frontend
- **React 19 & TypeScript**: UI rendering and static typing.
- **Vite**: Ultra-fast build tool and development server.
- **TailwindCSS v4**: Utility-first CSS pipeline for responsive design.
- Components communicate over HTTP REST alongside unidirectional persistent SSE channels.

### Infrastructure & DevOps
- **Docker & Docker Compose**: The entire system is strictly containerized. The `docker-compose.yml` orchestrates the Postgres database, Redis cache, FastAPI server, and dedicated Celery workers to mirror a production-grade topology.
