from enum import Enum
from typing import List, Optional
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator

class JobStatus(str, Enum):
    PENDING = "PENDING"
    TRANSCRIBING = "TRANSCRIBING"
    REVIEW_PENDING = "REVIEW_PENDING"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class SubtitleSegment(BaseModel):
    index: int = Field(..., ge=1, description="Sequence number of the subtitle")
    start_time_ms: int = Field(..., ge=0, description="Start time in milliseconds")
    end_time_ms: int = Field(..., ge=0, description="End time in milliseconds")
    text: str = Field(..., min_length=1, description="Text content of the subtitle")

    @model_validator(mode='after')
    def check_time_logic(self) -> 'SubtitleSegment':
        """Validates that the start time is strictly less than the end time."""
        if self.start_time_ms >= self.end_time_ms:
            raise ValueError("Start time must be strictly less than end time")
        return self

class RenderingParameters(BaseModel):
    brightness_increase: float = Field(
        default=0.05, 
        ge=-1.0, 
        le=1.0, 
        description="Brightness adjustment value for FFmpeg filter"
    )

class MediaJob(BaseModel):
    id: UUID = Field(default_factory=uuid4, description="Unique identifier of the job")
    original_filename: str = Field(..., min_length=1, description="Original filename uploaded")
    storage_blob_id: Optional[str] = Field(default=None, description="ID or path in Azure Blob Storage")
    status: JobStatus = Field(default=JobStatus.PENDING)
    subtitles: List[SubtitleSegment] = Field(default_factory=list)
    rendering_params: RenderingParameters = Field(default_factory=RenderingParameters)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

    def advance_status(self, new_status: JobStatus) -> None:
        """Controls the state transition of the job."""
        self.status = new_status