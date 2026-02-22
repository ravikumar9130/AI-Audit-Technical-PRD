"""
Audio normalization stage using FFmpeg.
"""
import os
import subprocess
from datetime import datetime
from typing import Tuple

from workers.celery_app import celery_app
from services.storage import get_storage_service
from core.config import get_settings
from core.database import get_db_context
from models import Call, ProcessingJob

settings = get_settings()


def _mark_stage_failed(call_id: int, job_id: int, error_msg: str, mark_call_failed: bool = False):
    with get_db_context() as db:
        job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        if job:
            job.status = "failed"
            job.finished_at = datetime.utcnow()
            job.error_message = error_msg
        if mark_call_failed:
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if call:
                call.status = "failed"
                call.error_message = error_msg
        db.commit()


@celery_app.task(bind=True, max_retries=3)
def normalize_audio_task(self, call_id: int, s3_path: str, work_dir: str) -> Tuple[int, str]:
    """
    Download audio from storage and normalize using FFmpeg.
    
    Returns:
        Tuple of (call_id, normalized_audio_path)
    """
    job_id = None
    
    try:
        # Log stage start
        with get_db_context() as db:
            job = ProcessingJob(
                call_id=call_id,
                stage="normalization",
                status="in_progress",
                celery_task_id=self.request.id,
                started_at=datetime.utcnow()
            )
            db.add(job)
            db.commit()
            job_id = job.job_id
        
        # Download file from storage
        storage = get_storage_service()
        input_path = os.path.join(work_dir, "input_audio")
        
        with open(input_path, 'wb') as f:
            storage.download_file(s3_path, f)
        
        # Determine input format
        input_ext = os.path.splitext(s3_path)[1].lower()
        if not input_ext:
            input_ext = ".wav"
        
        # Normalize using FFmpeg
        output_path = os.path.join(work_dir, "normalized.wav")
        
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-ar", str(settings.AUDIO_SAMPLE_RATE),  # 16 kHz
            "-ac", str(settings.AUDIO_CHANNELS),      # Mono
            "-c:a", settings.AUDIO_FORMAT,            # PCM 16-bit
            "-y",                                     # Overwrite output
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Get audio duration
        duration_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_path
        ]
        
        duration_result = subprocess.run(
            duration_cmd,
            capture_output=True,
            text=True
        )
        
        duration = float(duration_result.stdout.strip()) if duration_result.returncode == 0 else 0
        
        # Update call with duration
        with get_db_context() as db:
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if call:
                call.duration_seconds = int(duration)
            
            # Update job status
            job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if job:
                job.status = "completed"
                job.finished_at = datetime.utcnow()
                job.extra_metadata = {
                    "duration_seconds": duration,
                    "sample_rate": settings.AUDIO_SAMPLE_RATE,
                    "channels": settings.AUDIO_CHANNELS
                }
            
            db.commit()
        
        # Clean up input file
        if os.path.exists(input_path):
            os.remove(input_path)
        
        return (call_id, output_path)
        
    except subprocess.CalledProcessError as exc:
        error_msg = f"FFmpeg error: {exc.stderr}"
        give_up = self.request.retries >= self.max_retries
        _mark_stage_failed(call_id, job_id, error_msg, mark_call_failed=give_up)
        if give_up:
            raise
        raise self.retry(exc=exc, countdown=30)

    except Exception as exc:
        error_msg = str(exc)
        give_up = self.request.retries >= self.max_retries
        _mark_stage_failed(call_id, job_id, error_msg, mark_call_failed=give_up)
        if give_up:
            raise
        raise self.retry(exc=exc, countdown=30)
