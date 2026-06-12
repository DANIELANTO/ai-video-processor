import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "video_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.infrastructure.workers"]
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    # Safety time limits: prevents workers from blocking forever on hung I/O
    # (e.g., Azure upload timeout loops). SoftTimeLimitExceeded is raised at
    # 9 min so the task can clean up temp files and mark the job as FAILED
    # before the hard kill fires at 10 min.
    # (See spec: 2026-06-11-azure-upload-timeout-and-perf-overhaul.md, Phase 2)
    task_time_limit=600,        # Hard kill after 10 minutes
    task_soft_time_limit=540,   # Raise SoftTimeLimitExceeded after 9 minutes
)