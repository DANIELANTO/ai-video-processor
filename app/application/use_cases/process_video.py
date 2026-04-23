from uuid import UUID
from pydantic import BaseModel
from typing import List
from app.domain.entities import SubtitleSegment
from app.domain.entities import MediaJob, JobStatus
from app.application.interfaces import IMediaJobRepository, IFileStorage, IQueueService

class UploadVideoResponse(BaseModel):
    job_id: UUID
    upload_url: str
    status: JobStatus

class ProcessUploadedVideoUseCase:
    """Orchestrates the creation of the job and the generation of the direct upload URL to Azure."""
    def __init__(self, repository: IMediaJobRepository, storage: IFileStorage):
        self.repository = repository
        self.storage = storage

    def execute(self, filename: str) -> UploadVideoResponse:
        # 1. Instantiate the validated domain entity
        job = MediaJob(original_filename=filename)

        safe_filename = filename.replace(' ', '_')
        
        # 2. Define a safe naming convention for the Storage
        job.storage_blob_id = f"{job.id}_{safe_filename}"
        
        # 3. Request the signed URL through the port (interface)
        upload_url = self.storage.generate_upload_url(filename=job.storage_blob_id)
        
        # 4. Save the initial state in the repository
        self.repository.save(job)
        
        return UploadVideoResponse(
            job_id=job.id,
            upload_url=upload_url,
            status=job.status
        )

class ConfirmVideoUploadUseCase:
    """Orchestrates the state change once the client notifies that the file has been uploaded successfully."""
    def __init__(self, repository: IMediaJobRepository, queue: IQueueService):
        self.repository = repository
        self.queue = queue

    def execute(self, job_id: UUID) -> None:
        job = self.repository.get_by_id(job_id)
        if not job:
            raise ValueError(f"The job with ID {job_id} does not exist.")
            
        job.advance_status(JobStatus.TRANSCRIBING)
        self.repository.save(job)
        
        # Decouple the heavy processing by sending it to the queue
        self.queue.enqueue_transcription_task(job.id)

class SubmitFinalVideoRenderingUseCase:
    """Use case to receive edited subtitles and queue the final rendering."""
    def __init__(self, repository: IMediaJobRepository, queue: IQueueService):
        self.repository = repository
        self.queue = queue

    def execute(self, job_id: UUID, corrected_subtitles: List[SubtitleSegment]) -> None:
        job = self.repository.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")
        
        # Update the database with the subtitles that the user corrected in the UI
        job.subtitles = corrected_subtitles
        job.advance_status(JobStatus.RENDERING)
        self.repository.save(job)
        
        # It queues the heavy processing
        self.queue.enqueue_rendering_task(job.id)