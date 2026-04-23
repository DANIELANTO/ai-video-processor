from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, DateTime, Float, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
import os

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class MediaJobModel(Base):
    __tablename__ = "media_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename = Column(String, nullable=False)
    storage_blob_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="PENDING")
    
    # JSONB to store the structured list of subtitles
    subtitles = Column(JSONB, default=list)
    
    # Extract rendering parameters to facilitate future queries
    brightness_increase = Column(Float, default=0.05)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(String, nullable=True)