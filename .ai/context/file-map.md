# File Map — AI Video Processor

> **For AI Agents:** Use this file to locate where to make changes before touching any code.  
> Last updated: 2026-06-11

---

## Root Directory

```
ai-video-processor/
├── .ai/                          # AI Development Harness
├── app/                          # Backend Python source (DDD architecture)
├── frontend/                     # React + TypeScript + Vite frontend
├── venv/                         # Python virtual environment (DO NOT COMMIT)
├── .env                          # Secret environment variables (NOT committed)
├── .gitignore                    # Git ignore rules
├── Dockerfile                    # Backend container image definition
├── docker-compose.yml            # Multi-service orchestration
├── requirements.txt              # Python dependencies (pinned versions)
└── README.md                     # Project overview documentation
```

---

## Backend — `app/`

```
app/
├── __init__.py
├── domain/                       # Layer 1: Core business logic
│   ├── __init__.py
│   └── entities.py               # ALL domain entities (MediaJob, SubtitleSegment, etc.)
│
├── application/                  # Layer 2: Use cases + interface definitions
│   ├── __init__.py
│   ├── interfaces.py             # Abstract ports: IMediaJobRepository, IFileStorage, IQueueService, IEventStreamService
│   ├── interfaces/               # ⚠️ UNUSED DIRECTORY — appears to be an artifact, do not use
│   └── use_cases/
│       ├── __init__.py
│       └── process_video.py      # All use cases: ProcessUploadedVideoUseCase, ConfirmVideoUploadUseCase, SubmitFinalVideoRenderingUseCase
│
├── infrastructure/               # Layer 3: External adapters
│   ├── celery_app.py             # Celery instance and configuration
│   ├── database.py               # SQLAlchemy engine, session, Base, MediaJobModel (ORM)
│   ├── pubsub.py                 # RedisEventStreamAdapter — SSE async generator
│   ├── queue.py                  # CeleryQueueAdapter — task enqueueing
│   ├── repositories.py           # PostgresMediaJobRepository — ORM ↔ domain mapping
│   ├── storage.py                # AzureBlobStorageAdapter — upload/download/SAS generation
│   └── workers.py                # Celery tasks: transcribe_audio, render_video (heavy I/O)
│
└── presentation/                 # Layer 4: HTTP interface
    └── main.py                   # FastAPI app, all endpoints, DI providers, DTOs
```

### Per-File Responsibilities

| File | Purpose | Modify for |
|---|---|---|
| `domain/entities.py` | Business entities, state machine, validation rules | New domain concepts, business rule changes |
| `application/interfaces.py` | Port contracts (ABCs) | Adding new infrastructure capabilities |
| `application/use_cases/process_video.py` | Business workflows | New business actions or workflow changes |
| `infrastructure/database.py` | ORM model + DB connection | Schema changes (add columns), DB config |
| `infrastructure/repositories.py` | CRUD + domain↔ORM mapping | DB query changes, new fields to persist |
| `infrastructure/storage.py` | Azure Blob operations | Storage behavior changes, new blob operations |
| `infrastructure/celery_app.py` | Celery config | Queue config, new queues, serializer changes |
| `infrastructure/queue.py` | Task enqueueing logic | New background task types |
| `infrastructure/pubsub.py` | Redis SSE stream adapter | Stream behavior, reconnect logic |
| `infrastructure/workers.py` | Heavy async tasks | Transcription logic, rendering logic, progress tracking |
| `presentation/main.py` | All HTTP routes + DI | New endpoints, CORS config, new request DTOs |

### ⚠️ Files That Require Extra Care

| File | Risk |
|---|---|
| `infrastructure/workers.py` | Directly handles binary I/O; bugs here cause failed jobs and orphaned temp files |
| `infrastructure/database.py` | Schema is applied via `create_all()` — no migrations. Column additions require care |
| `presentation/main.py` | Single file for all routes; adding routes should be done with clear naming |
| `domain/entities.py` | Pydantic models used across all layers; breaking changes here affect everything |

---

## Frontend — `frontend/src/`

```
frontend/
├── .env                          # Frontend env vars (VITE_API_BASE_URL)
├── index.html                    # HTML entrypoint
├── vite.config.ts                # Vite build configuration
├── tsconfig.json                 # TypeScript root config
├── tsconfig.app.json             # TypeScript app config
├── tsconfig.node.json            # TypeScript node config
├── eslint.config.js              # ESLint rules
├── package.json                  # NPM dependencies + scripts
└── src/
    ├── main.tsx                  # React app entrypoint (renders <App />)
    ├── App.tsx                   # Root component — manages job state machine and renders views
    ├── App.css                   # App-level CSS (currently minimal)
    ├── index.css                 # Global CSS reset + TailwindCSS v4 import
    ├── assets/                   # Static assets (images, icons)
    ├── components/
    │   └── SubtitleEditor.tsx    # Subtitle review/edit UI — table of editable rows
    ├── hooks/
    │   ├── useJobStream.ts       # SSE connection management + stream state (status, progress, final_url)
    │   └── useSubtitleEditor.ts  # Subtitle list state management (add, remove, edit rows)
    ├── services/
    │   └── api.ts                # API client — all HTTP calls to FastAPI backend
    └── utils/                    # Shared utility functions (currently empty or minimal)
```

### Per-File Responsibilities

| File | Purpose | Modify for |
|---|---|---|
| `App.tsx` | Job state machine, UI phase switching (upload → processing → review → complete) | New UI phases, global state changes |
| `components/SubtitleEditor.tsx` | Subtitle review editor UI | Editing UX improvements, new subtitle fields |
| `hooks/useJobStream.ts` | SSE management, status/progress tracking | New SSE event types, reconnect logic |
| `hooks/useSubtitleEditor.ts` | Subtitle list state (CRUD in memory) | Subtitle manipulation features |
| `services/api.ts` | All backend API calls (upload, confirm, render, get details) | New API endpoints, request/response shape changes |
| `index.css` | TailwindCSS v4 import + global reset | Global styles, design tokens |

---

## DevOps & Configuration Files

| File | Purpose | Modify for |
|---|---|---|
| `Dockerfile` | Builds backend image (Python 3.11 + FFmpeg + dependencies) | New system packages, Python version change |
| `docker-compose.yml` | Wires all services: api, db, redis, worker | New services, port changes, env var changes |
| `requirements.txt` | Pinned Python dependencies | Adding/updating Python packages |
| `frontend/package.json` | NPM dependencies + build scripts | Adding/updating frontend packages |
| `.gitignore` | Git ignore rules | Excluding new generated files |
| `.env` | Runtime secrets (never committed) | Adding new environment variables |

---

## The `.ai/` Harness

```
.ai/
├── agent-instructions.md         # Mandatory protocol for all AI agents
├── context/
│   ├── project-context.md        # High-level overview: what, how, tech stack
│   ├── architecture-design.md    # DDD layers, data flow, patterns, risks
│   ├── file-map.md               # THIS FILE — where everything lives
│   ├── development-guidelines.md # Conventions, code style, how to add features
│   └── decisions.md              # ADR log — why key decisions were made
└── specs/
    ├── README.md                 # How to use the spec-driven workflow
    ├── spec-template.md          # Template for new feature specs
    └── [YYYY-MM-DD-feature.md]  # Individual feature/change specs
```

---

## File Map Update Policy

This file must be updated when:
- A new file or folder is added to the project.
- A file is renamed or moved.
- A new layer or module is introduced.
- The responsibilities of an existing file change significantly.
- A new frontend component, hook, or service is created.
- The `.ai/` structure itself is modified.
