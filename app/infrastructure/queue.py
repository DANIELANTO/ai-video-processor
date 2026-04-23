from uuid import UUID
from app.application.interfaces import IQueueService
from app.infrastructure.celery_app import celery_app

class CeleryQueueAdapter(IQueueService):
    def enqueue_transcription_task(self, job_id: UUID) -> None:
        celery_app.send_task("app.infrastructure.workers.transcribe_audio", args=[str(job_id)])

    def enqueue_rendering_task(self, job_id: UUID) -> None:
        celery_app.send_task("app.infrastructure.workers.render_video", args=[str(job_id)])