from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from app.domain.entities import MediaJob
from typing import AsyncGenerator

class IMediaJobRepository(ABC):
    @abstractmethod
    def save(self, job: MediaJob) -> None:
        """Persists or updates a MediaJob in the database."""
        pass

    @abstractmethod
    def get_by_id(self, job_id: UUID) -> Optional[MediaJob]:
        """Retrieves a MediaJob by its unique ID."""
        pass

class IFileStorage(ABC):
    @abstractmethod
    def generate_upload_url(self, filename: str) -> str:
        """Generates a temporary URL with write permissions (e.g., SAS Token)."""
        pass

    @abstractmethod
    def download_file(self, blob_name: str, local_path: str) -> None:
        """Downloads a blob from Azure to the container's local storage using chunks to optimize memory RAM."""
        pass

    @abstractmethod
    def upload_file(self, local_path: str, blob_name: str) -> str:
        """Uploads a local file to Azure Blob Storage and returns the URL (without token)."""
        pass

class IQueueService(ABC):
    @abstractmethod
    def enqueue_transcription_task(self, job_id: UUID) -> None:
        """Sends the job ID to the Redis queue for Whisper workers."""
        pass

    @abstractmethod
    def enqueue_rendering_task(self, job_id: UUID) -> None:
        """Sends the job ID to the Redis queue for FFmpeg workers."""
        pass

class IEventStreamService(ABC):
    @abstractmethod
    async def subscribe_to_job_events(self, job_id: str) -> AsyncGenerator[dict, None]:
        """Subscribes to job events and yields them as a stream."""
        pass