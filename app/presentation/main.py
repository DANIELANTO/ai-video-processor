import os
import json
import redis.asyncio as redis_async
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.application.interfaces import IEventStreamService
from app.infrastructure.pubsub import RedisEventStreamAdapter

import app.infrastructure.database as _db_module
from app.infrastructure.repositories import PostgresMediaJobRepository
from app.infrastructure.storage import AzureBlobStorageAdapter
from app.application.use_cases.process_video import ProcessUploadedVideoUseCase

from uuid import UUID
from app.infrastructure.queue import CeleryQueueAdapter
from app.application.use_cases.process_video import ConfirmVideoUploadUseCase

from typing import List
from app.domain.entities import SubtitleSegment, MediaJob, JobStatus
from app.application.use_cases.process_video import SubmitFinalVideoRenderingUseCase

from fastapi.middleware.cors import CORSMiddleware


# ---------------------------------------------------------------------------
# Lifespan — runs AFTER Docker networking is ready, not at import time.
# This is the correct place to establish the DB connection and create tables.
# Calling Base.metadata.create_all() at module level caused a race condition
# with Docker's internal DNS resolver before the "db" container was reachable.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    _db_module.init_db()                                    # connect with retry
    _db_module.Base.metadata.create_all(bind=_db_module.engine)  # create tables
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────────
    # Nothing to tear down for now; SQLAlchemy manages connection pool lifecycle.


app = FastAPI(title="Video AI Processing API", version="1.0.0", lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
def get_db():
    db = _db_module.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_storage_adapter():
    return AzureBlobStorageAdapter(
        connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        container_name=os.getenv("AZURE_CONTAINER_NAME"),
        account_name=os.getenv("AZURE_ACCOUNT_NAME"),
        account_key=os.getenv("AZURE_ACCOUNT_KEY")
    )


def get_queue_service():
    return CeleryQueueAdapter()


def get_stream_service() -> IEventStreamService:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return RedisEventStreamAdapter(redis_url=redis_url)


# ---------------------------------------------------------------------------
# Input Schemas (DTOs)
# ---------------------------------------------------------------------------
class UploadVideoRequest(BaseModel):
    filename: str


class RenderVideoRequest(BaseModel):
    corrected_subtitles: List[SubtitleSegment]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/v1/jobs/upload", status_code=201)
def request_upload(
    request: UploadVideoRequest,
    db: Session = Depends(get_db),
    storage: AzureBlobStorageAdapter = Depends(get_storage_adapter)
):
    """
    Starts a new video job and returns the URL (SAS Token)
    so that the client can upload the file directly to Azure Blob Storage.
    """
    try:
        repository = PostgresMediaJobRepository(db)
        use_case = ProcessUploadedVideoUseCase(repository=repository, storage=storage)
        response = use_case.execute(filename=request.filename)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/api/v1/jobs/{job_id}/confirm-upload", status_code=200)
def confirm_upload(
    job_id: UUID,
    db: Session = Depends(get_db),
    queue: CeleryQueueAdapter = Depends(get_queue_service)
):
    """
    Endpoint called by the client when the upload to Azure is finished.
    """
    try:
        repository = PostgresMediaJobRepository(db)
        use_case = ConfirmVideoUploadUseCase(repository=repository, queue=queue)
        use_case.execute(job_id=job_id)
        return {"message": "Upload confirmado. Transcripción encolada."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/api/v1/jobs/{job_id}/stream")
async def job_status_stream(
    job_id: str,
    stream_service: IEventStreamService = Depends(get_stream_service)
):
    """
    SSE endpoint that consumes pure events from the infrastructure
    and formats them to be transmitted to the frontend.
    """
    async def sse_formatter():
        async for event in stream_service.subscribe_to_job_events(job_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(sse_formatter(), media_type="text/event-stream")


@app.post("/api/v1/jobs/{job_id}/render", status_code=202)
def submit_render(
    job_id: UUID,
    request: RenderVideoRequest,
    db: Session = Depends(get_db),
    queue: CeleryQueueAdapter = Depends(get_queue_service)
):
    """
    Receives the corrected subtitles from the frontend editor and starts the rendering.
    """
    try:
        repository = PostgresMediaJobRepository(db)
        use_case = SubmitFinalVideoRenderingUseCase(repository=repository, queue=queue)
        use_case.execute(job_id=job_id, corrected_subtitles=request.corrected_subtitles)
        return {"message": "Rendering queued successfully."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/jobs/{job_id}", status_code=200, response_model=MediaJob)
def get_job_details(
    job_id: UUID,
    db: Session = Depends(get_db),
    storage: AzureBlobStorageAdapter = Depends(get_storage_adapter)
):
    """
    Returns the details of a specific job, including its subtitles and final URL if completed.
    """
    try:
        repository = PostgresMediaJobRepository(db)
        job = repository.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

        if job.status == JobStatus.COMPLETED and job.storage_blob_id:
            final_blob_name = f"final_{job.storage_blob_id}"
            job.final_url = storage.generate_read_url(final_blob_name)

        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")