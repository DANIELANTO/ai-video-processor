from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, DateTime, Float, create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
import os
import time
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/videodb")

# Lazily initialized — set by init_db() at application startup (lifespan).
# Do NOT call create_engine() at module import time: Docker's internal DNS for
# the "db" service may not be resolvable yet when Python first imports this module.
engine = None
SessionLocal = None


def _create_engine_with_retry(url: str, retries: int = 10, delay: int = 3):
    """Creates the SQLAlchemy engine, retrying until the DB is reachable.
    Prevents crashes when Docker's internal DNS for 'db' hasn't resolved yet
    or Postgres is still initializing.
    """
    for attempt in range(1, retries + 1):
        try:
            _engine = create_engine(url, pool_pre_ping=True)
            # Lightweight probe: execute a trivial query to confirm connectivity
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection established on attempt %d.", attempt)
            return _engine
        except Exception as exc:
            logger.warning(
                "DB not ready (attempt %d/%d): %s. Retrying in %ds…",
                attempt, retries, exc, delay
            )
            if attempt == retries:
                raise
            time.sleep(delay)


def init_db():
    """Initialises the engine and session factory.

    Must be called once during application startup (e.g. from the FastAPI
    lifespan handler), after Docker networking is guaranteed to be available.
    Calling this at module import time caused race conditions with Docker DNS.
    """
    global engine, SessionLocal
    engine = _create_engine_with_retry(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("SessionLocal factory initialised.")


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