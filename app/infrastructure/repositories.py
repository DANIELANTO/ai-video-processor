from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.domain.entities import MediaJob, JobStatus, SubtitleSegment, RenderingParameters
from app.application.interfaces import IMediaJobRepository
from app.infrastructure.database import MediaJobModel

class PostgresMediaJobRepository(IMediaJobRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, job: MediaJob) -> None:
        db_job = self.session.query(MediaJobModel).filter_by(id=job.id).first()
        
        if not db_job:
            db_job = MediaJobModel(id=job.id)
            self.session.add(db_job)
        
        db_job.original_filename = job.original_filename
        db_job.storage_blob_id = job.storage_blob_id
        db_job.status = job.status.value
        # Serialize Pydantic objects to a list of dictionaries for JSONB
        db_job.subtitles = [sub.model_dump() for sub in job.subtitles]
        db_job.brightness_increase = job.rendering_params.brightness_increase
        db_job.created_at = job.created_at
        db_job.error_message = job.error_message
        
        self.session.commit()

    def get_by_id(self, job_id: UUID) -> Optional[MediaJob]:
        db_job = self.session.query(MediaJobModel).filter_by(id=job_id).first()
        
        if not db_job:
            return None
        
        return MediaJob(
            id=db_job.id,
            original_filename=db_job.original_filename,
            storage_blob_id=db_job.storage_blob_id,
            status=JobStatus(db_job.status),
            subtitles=[SubtitleSegment(**sub) for sub in db_job.subtitles],
            rendering_params=RenderingParameters(brightness_increase=db_job.brightness_increase),
            created_at=db_job.created_at,
            error_message=db_job.error_message
        )