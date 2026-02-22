"""
Main pipeline orchestrator for call processing.
"""
import os
import tempfile
import shutil
from datetime import datetime
from typing import Dict, Any, Optional

from celery import chain

from workers.celery_app import celery_app
from workers.stages.normalize import normalize_audio_task
from workers.stages.vad import run_vad_task
from workers.stages.diarize import run_diarization_task
from workers.stages.transcribe import run_transcription_task
from workers.stages.score import run_llm_scoring_task
from core.database import get_db_context
from core.config import get_settings
from models import Call, ProcessingJob

settings = get_settings()


@celery_app.task(bind=True, max_retries=3)
def process_call_task(self, call_id: int, s3_path: str, template_id: int):
    """
    Main entry point for processing a call through the ML pipeline.
    
    Creates a Celery chain to process the call through all stages:
    1. Audio normalization
    2. Voice Activity Detection
    3. Speaker diarization
    4. ASR transcription
    5. LLM scoring
    """
    try:
        # Update call status
        with get_db_context() as db:
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if not call:
                raise ValueError(f"Call {call_id} not found")
            
            call.status = "processing"
            call.processing_started_at = datetime.utcnow()
            
            # Create initial processing job
            job = ProcessingJob(
                call_id=call_id,
                stage="uploaded",
                status="completed",
                celery_task_id=self.request.id,
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow()
            )
            db.add(job)
            db.commit()
        
        # Create temporary working directory
        work_dir = tempfile.mkdtemp(prefix=f"call_{call_id}_")
        
        try:
            # Define the pipeline chain
            pipeline = chain(
                normalize_audio_task.s(call_id, s3_path, work_dir),
                run_vad_task.s(call_id, work_dir),
                run_diarization_task.s(call_id, work_dir),
                run_transcription_task.s(call_id, work_dir, template_id),
                run_llm_scoring_task.s(call_id, work_dir, template_id)
            )
            
            # Execute pipeline with error callback to mark call as failed
            error_callback = update_call_status.si(call_id, "failed", "Pipeline stage failed")
            pipeline_result = pipeline.apply_async(link_error=error_callback)
            
            return {
                "call_id": call_id,
                "pipeline_task_id": pipeline_result.id,
                "status": "pipeline_started",
                "work_dir": work_dir
            }
            
        except Exception as exc:
            # Cleanup on failure
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
            raise self.retry(exc=exc, countdown=60)
            
    except Exception as exc:
        # Update call status on failure
        with get_db_context() as db:
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if call:
                call.status = "failed"
                call.error_message = str(exc)
                db.commit()
        
        raise


@celery_app.task
def update_call_status(call_id: int, status: str, error_message: Optional[str] = None):
    """Update call status in database."""
    with get_db_context() as db:
        call = db.query(Call).filter(Call.call_id == call_id).first()
        if call:
            call.status = status
            if error_message:
                call.error_message = error_message
            if status == "completed":
                call.processing_completed_at = datetime.utcnow()
            db.commit()


@celery_app.task
def log_processing_stage(
    call_id: int,
    stage: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None
):
    """Log a processing stage completion/failure."""
    with get_db_context() as db:
        job = ProcessingJob(
            call_id=call_id,
            stage=stage,
            status=status,
            extra_metadata=metadata,
            error_message=error_message,
            finished_at=datetime.utcnow() if status in ["completed", "failed"] else None
        )
        db.add(job)
        db.commit()
