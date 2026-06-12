# Spec: Fix Critical Infrastructure Boot Errors

**Date:** 2026-06-11  
**Author:** AI Agent  
**Status:** Implemented  
**Type:** Bug fix (multi-module)

---

## 1. Context and Problem

When booting the stack with `docker compose up --build`, four errors are detected that prevent the services from starting correctly. During implementation, two additional unforeseen bugs emerged (Error 5 and Error 6).

### Error 1 — API cannot resolve host "db" (DNS / timing)
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError)
could not translate host name "db" to address: Temporary failure in name resolution
```
**Root cause:** `database.py` calls `_create_engine_with_retry()` at module import time. When `main.py` is imported by Uvicorn, the `database.py` module executes immediately. At that moment, Docker's internal network may not be ready yet. `depends_on: condition: service_healthy` does not guarantee that Docker's internal DNS is propagated at the exact moment of the first Python import.

**Fix:** Refactor `database.py` to use lazy initialization (`engine = None`, `SessionLocal = None`). A new `init_db()` function performs the actual connection. `main.py` calls `init_db()` inside a FastAPI lifespan handler, which runs after Uvicorn is up and running and the Docker network is guaranteed to be ready. (See DEC-0011 in `decisions.md`.)

---

### Error 2 — `redis.asyncio` not found
```
Cannot find module 'redis.asyncio'
```
**Root cause:** Cached Docker image with an older version of `redis`. The `redis==7.4.0` library in `requirements.txt` DOES include `redis.asyncio`.

**Fix:** Clean rebuild with `--no-cache`. No code changes required.

---

### Error 3 — Frontend receives 404 on `POST /api/v1/jobs/upload`
```
:8000/api/v1/jobs/upload:1 Failed to load resource: 404
```
**Root cause:** Cascading consequence of Error 1. The API never started. The route exists and is correct.

**Fix:** Resolved by fixing Error 1. No frontend changes required.

---

### Error 4 — Celery SecurityWarning (root user)
```
SecurityWarning: You're running the worker with superuser privileges
```
**Root cause:** The Dockerfile does not create a non-root user.

**Fix:** Set `C_FORCE_ROOT=1` in the `worker_whisper` service in `docker-compose.yml`. Technical debt: create a non-root user in the Dockerfile in a future spec.

---

### Error 5 — Port 8000 conflict (discovered during implementation)
```
Bind for 0.0.0.0:8000 failed: port is already allocated
```
**Root cause:** The `nodepay-ai-service-1` container (another project in the same environment) occupies port 8000 on the host.

**Fix:** Change the host port mapping from `8000:8000` to `8001:8000` in `docker-compose.yml`. Update `VITE_API_BASE_URL` in `frontend/.env` to `localhost:8001`. Update the hardcoded fallbacks in `api.ts` and `useJobStream.ts`.

---

### Error 6 — Worker fails with `TypeError: 'NoneType' object is not callable` (discovered post-implementation)
```
TypeError: 'NoneType' object is not callable
  File "/workspace/app/infrastructure/workers.py", line 55, in transcribe_audio
    db = SessionLocal()
```
**Root cause:** The lazy initialization refactoring left `SessionLocal = None` at the module level. The Celery worker runs in its **own separate process**, imports `database.py` directly, and **never passes through the FastAPI lifespan**, so `init_db()` is never executed in the worker process. When the task tries to call `SessionLocal()`, it fails because it remains `None`.

**Fix:** Call `init_db()` explicitly in `workers.py` at the module level (after imports). The `worker_whisper` container already depends on `db: condition: service_healthy`, so the DB is guaranteed to be available when the worker starts.

---

## 2. Affected Files

| File | Change |
|---|---|
| `app/infrastructure/database.py` | Lazy init: `engine = None`, `SessionLocal = None`, new `init_db()` function |
| `app/presentation/main.py` | FastAPI lifespan handler that calls `init_db()` + `create_all()` |
| `app/infrastructure/workers.py` | Explicit call to `init_db()` at module level |
| `docker-compose.yml` | Port `8001:8000`, `C_FORCE_ROOT=1`, `restart: on-failure`, `REDIS_URL` in api |
| `frontend/.env` | `VITE_API_BASE_URL` → `localhost:8001` |
| `frontend/src/services/api.ts` | Hardcoded fallback `8000→8001` |
| `frontend/src/hooks/useJobStream.ts` | Hardcoded fallback `8000→8001` |

---

## 3. Acceptance Criteria

- [x] `docker compose up` brings up all services without fatal errors.
- [x] The API responds at `http://localhost:8001/docs`.
- [x] `POST /api/v1/jobs/upload` returns 201.
- [x] The Celery worker completes `transcribe_audio` without `TypeError`.
- [x] The Celery SecurityWarning warning does not stop the worker.
- [x] `redis.asyncio` imports correctly.
- [x] The UI transitions from the "Analyzing audio" state to the subtitle review state.

---

## 4. Azure Testing (Manual)

Once the services are running:
1. Call `POST /api/v1/jobs/upload` with `{"filename": "test.mp4"}`.
2. Verify that the response includes an `upload_url` with a `*.blob.core.windows.net` domain.
3. Confirm that the Azure container (`AZURE_CONTAINER_NAME`) receives the blob.
4. Confirm that `transcribe_audio` completes and the UI shows the subtitle editor.

---

## 5. Implementation Notes

- `DEC-0011` recorded in `decisions.md` documents the lazy init decision.
- The host port for the API is now 8001 (permanent change while `nodepay-ai-service` coexists in the same environment).
- The worker needs to call `init_db()` independently because it runs in a separate process from FastAPI.
- `project-context.md` updated: API port, new mapped port.
