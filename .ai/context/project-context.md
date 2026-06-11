# Project Context — AI Video Processor

> **For AI Agents:** Read this file first to understand the project before making any change.  
> Last updated: 2026-06-11

---

## 1. Project Name & Purpose

**Name:** AI Video Processor  
**Type:** Full-stack web application — AI-powered video processing pipeline

**Primary Purpose:**  
An end-to-end system that takes a user-uploaded video and:
1. Generates accurate, timestamp-granular subtitles using OpenAI Whisper.
2. Lets the user review and correct the transcription in a web editor.
3. Burns the corrected subtitles into the video using FFmpeg and applies brightness equalization.
4. Uploads the final rendered video to Azure Blob Storage and provides a download link.

The system is designed for asynchronous, high-throughput video processing and is built to be production-grade from the start.

---

## 2. Technology Stack

### Backend
| Technology | Version (pinned) | Role |
|---|---|---|
| Python | 3.11 (Docker) | Runtime |
| FastAPI | 0.136.0 | HTTP API framework |
| SQLAlchemy | 2.0.49 | ORM |
| PostgreSQL | 15 | Primary database (persistence) |
| Celery | 5.6.3 | Distributed task queue |
| Redis | 7 | Message broker, result backend & Pub/Sub for SSE |
| OpenAI Whisper | API `whisper-1` | AI transcription |
| FFmpeg | System (Docker) | Audio extraction & video rendering |
| Azure Blob Storage SDK | 12.28.0 | Cloud file storage |
| Pydantic | 2.13.1 | Data validation & domain models |
| Uvicorn | 0.44.0 | ASGI server |
| httpx | 0.27.2 | HTTP client for OpenAI |

### Frontend
| Technology | Version | Role |
|---|---|---|
| React | 19 | UI library |
| TypeScript | ~6.0.2 | Static typing |
| Vite | ^8.0.9 | Build tool & dev server |
| TailwindCSS | v4 | Utility-first CSS |

### Infrastructure & DevOps
| Technology | Role |
|---|---|
| Docker | Container runtime |
| Docker Compose | Multi-service orchestration |

---

## 3. Architecture Style

The project implements **Domain-Driven Design (DDD)** with **Clean Architecture / Hexagonal Architecture**.

- **The domain layer is completely isolated** from frameworks, databases, and external APIs.
- Dependency direction always flows **inward** (toward the domain), never outward.
- External adapters implement interfaces (ports) defined in the application layer.
- Dependency Injection is managed manually via FastAPI's `Depends` system.

See `.ai/context/architecture-design.md` for a detailed breakdown.

---

## 4. How to Run the Project

### Prerequisites
- Docker & Docker Compose installed
- A `.env` file at the project root with all required secrets (see Section 6)

### Start the full system
```bash
docker compose up --build
```

This starts:
- `video_processor_api` — FastAPI on port `8001` (host) → `8000` (internal). Changed from 8000 due to port conflict with `nodepay-ai-service` in the same dev environment.
- `video_processor_db` — PostgreSQL on port `5433` (mapped from internal `5432`)
- `video_processor_redis` — Redis on port `6380` (mapped from internal `6379`)
- `video_worker_whisper` — Celery worker (Whisper + FFmpeg)

### Start the frontend (development)
```bash
cd frontend
npm run dev
```

Frontend dev server runs on `http://localhost:5173`. API is at `http://localhost:8001`.

### Run backend locally (without Docker)
```bash
source .env
pip install -r requirements.txt
uvicorn app.presentation.main:app --reload
```

---

## 5. Important Commands

| Command | What it does |
|---|---|
| `docker compose up --build` | Rebuild and start all services |
| `docker compose up` | Start all services (no rebuild) |
| `docker compose down` | Stop all services |
| `cd frontend && npm run dev` | Start frontend dev server |
| `cd frontend && npm run build` | Build frontend for production |
| `cd frontend && npm run lint` | Run ESLint on frontend |
| `celery -A app.infrastructure.celery_app worker --loglevel=info` | Start Celery worker manually |

---

## 6. Environment Variables

Required variables (must be present in the `.env` file at project root):

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `AZURE_STORAGE_CONNECTION_STRING` | Full Azure Blob Storage connection string |
| `AZURE_CONTAINER_NAME` | Azure container name for video blobs |
| `AZURE_ACCOUNT_NAME` | Azure storage account name |
| `AZURE_ACCOUNT_KEY` | Azure storage account key |
| `REDIS_URL` | Redis connection URL (e.g., `redis://redis:6379/0`) |
| `OPENAI_API_KEY` | OpenAI API key for Whisper |

**Note:** The `.env` file is in `.gitignore` and must be created manually.  
The frontend has its own `.env` at `frontend/.env` with `VITE_API_BASE_URL` (currently set to an empty string, so it uses the dev proxy or same origin).

> ⚠️ **Security Warning for Agents:** Never log, expose, or commit secrets. Do not read `.env` values into documentation verbatim.

---

## 7. Project Structure Summary

```
ai-video-processor/
├── .ai/                          # AI Development Harness (THIS FOLDER)
├── app/                          # Backend Python application
│   ├── domain/                   # Core business entities (no dependencies)
│   ├── application/              # Use cases + interface definitions (ports)
│   ├── infrastructure/           # Adapters: DB, Storage, Queue, Workers, PubSub
│   └── presentation/             # FastAPI HTTP layer (routes, DTOs, DI)
├── frontend/                     # React + TypeScript + Vite + TailwindCSS v4
│   └── src/
│       ├── components/           # UI components (SubtitleEditor)
│       ├── hooks/                # Custom React hooks (useJobStream, useSubtitleEditor)
│       ├── services/             # API client (api.ts)
│       └── utils/                # Utility functions
├── Dockerfile                    # Backend container definition
├── docker-compose.yml            # Multi-service orchestration
├── requirements.txt              # Python dependencies (pinned)
└── .env                          # Secrets (NOT committed)
```

See `.ai/context/file-map.md` for detailed per-file descriptions.

---

## 8. Current Project State

- **Status:** Functional MVP — core pipeline works end-to-end.
- **Missing:** No automated tests (unit, integration, or e2e). No Alembic migrations (tables are created via `Base.metadata.create_all()`). No authentication/authorization. No job listing UI (only single active job via `localStorage`).
- **Frontend:** Minimal, functional UI. Uses TailwindCSS v4 utility classes directly in JSX.
- **Backend:** Well-structured, clean architecture. Exception handling is basic (`try/except` + HTTP 500).
- **No CI/CD pipeline** detected.

---

## 9. Pending — To Be Confirmed

- [ ] Is there a `.env.example` file planned? Currently there is no template file.
- [ ] Is there a planned migration to Alembic for database schema management?
- [ ] Is there a test suite planned? No tests detected anywhere.
- [ ] Is the `app/application/interfaces/` folder (directory) used or is `interfaces.py` (file) the canonical location? Both exist — the directory appears to be empty/unused.
- [ ] Are there plans to add user authentication (JWT, sessions, etc.)?
- [ ] Is `final_url` supposed to be stored in the DB or always regenerated on read? Currently it is regenerated at read time.
- [ ] Is the frontend planned to remain a SPA or will routing be added?

---

## 10. Context Update Trigger

This file must be updated when:
- A new feature is added that changes how the system is run or configured.
- A new environment variable is introduced or removed.
- The tech stack changes (new or removed dependencies).
- The project structure changes significantly.
- A spec is implemented that modifies the described workflow.
- A direct user prompt introduces information relevant to future agents.
