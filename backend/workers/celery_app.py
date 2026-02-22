"""
Celery application configuration.
"""
import workers._torch_patch  # noqa: F401 - must run before any code that loads torch/pyannote
from celery import Celery
from celery.signals import task_failure, task_success, task_retry, worker_process_init

from core.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "audit_ai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "workers.pipeline",
        "workers.stages.normalize",
        "workers.stages.vad",
        "workers.stages.diarize",
        "workers.stages.transcribe",
        "workers.stages.score",
        "workers.retention"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=500,  # Restart worker after 500 tasks (keep ML models cached longer)
    
    # Result backend
    result_expires=3600 * 24 * 7,  # Results expire after 7 days
    result_extended=True,
    
    # Retries
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
)


@worker_process_init.connect
def _apply_torch_patch(**kwargs):
    import workers._torch_patch  # noqa: F401 - re-apply in each worker process (fork/spawn)
    workers._torch_patch.apply_patch()


@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, **kw):
    """Handle task failures."""
    from core.database import get_db_context
    from models import ProcessingJob, Call
    
    try:
        call_id = kwargs.get("call_id")
        if not call_id and args:
            first = args[0]
            if isinstance(first, int):
                call_id = first
            elif isinstance(first, (tuple, list)) and len(first) > 0:
                # Chain tasks: args = (previous_result, call_id, ...)
                call_id = args[1] if len(args) > 1 and isinstance(args[1], int) else first[0]

        if call_id is not None:
            try:
                call_id = int(call_id)
            except (TypeError, ValueError):
                call_id = None

        if call_id is not None:
            with get_db_context() as db:
                # Update call status
                call = db.query(Call).filter(Call.call_id == call_id).first()
                if call:
                    call.status = "failed"
                    call.error_message = str(exception)
                
                # Update processing job
                job = db.query(ProcessingJob).filter(
                    ProcessingJob.celery_task_id == task_id
                ).first()
                if job:
                    job.status = "failed"
                    job.finished_at = __import__('datetime').datetime.utcnow()
                    job.error_message = str(exception)
                
                db.commit()
    except Exception as e:
        print(f"Failed to handle task failure: {e}")


@task_success.connect
def handle_task_success(sender=None, result=None, **kwargs):
    """Handle task success."""
    pass  # Pipeline stages handle their own success updates


@task_retry.connect
def handle_task_retry(sender=None, request=None, reason=None, **kwargs):
    """Handle task retry."""
    print(f"Task {request.id} retrying: {reason}")
