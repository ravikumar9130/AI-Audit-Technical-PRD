"""
ASR Transcription stage using Faster-Whisper.
"""
import os
from datetime import datetime
from typing import Tuple, List, Dict, Any

from workers.celery_app import celery_app
from core.config import get_settings
from core.database import get_db_context
from models import Call, ProcessingJob, Transcript

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

# Global Whisper model (loaded once per worker)
_whisper_model = None

def get_whisper_model():
    """Get or load Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            import torch

            use_cpu = os.environ.get("USE_CPU_LLM", "").lower() in ("1", "true", "yes")
            device = "cpu" if use_cpu else ("cuda" if torch.cuda.is_available() else "cpu")
            compute_type = "float16" if device == "cuda" else "int8"
            # Use smaller model on CPU for much faster inference (~20x speedup)
            model_size = "base" if device == "cpu" else "large-v3"
            
            _whisper_model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type
            )
        except Exception as e:
            print(f"Failed to load Whisper model: {e}")
            raise
    
    return _whisper_model


TRANSCRIBE_SOFT_TIME_LIMIT = 10 * 60
TRANSCRIBE_TIME_LIMIT = 15 * 60

@celery_app.task(bind=True, max_retries=3, soft_time_limit=TRANSCRIBE_SOFT_TIME_LIMIT, time_limit=TRANSCRIBE_TIME_LIMIT)
def run_transcription_task(self, previous_result: Tuple[int, str, List[Dict]], call_id: int, work_dir: str, template_id: int) -> Tuple[int, str, str]:
    """
    Transcribe audio using Whisper and assign speakers.
    
    Args:
        previous_result: Tuple of (call_id, audio_path, diarized_segments) from diarization
        
    Returns:
        Tuple of (call_id, transcript_text, full_transcript_with_speakers)
    """
    _, audio_path, diarized_segments = previous_result
    job_id = None
    
    try:
        # Log stage start
        with get_db_context() as db:
            job = ProcessingJob(
                call_id=call_id,
                stage="transcription",
                status="in_progress",
                celery_task_id=self.request.id,
                started_at=datetime.utcnow()
            )
            db.add(job)
            db.commit()
            job_id = job.job_id
        
        # Get model
        model = get_whisper_model()
        
        segments, info = model.transcribe(
            audio_path,
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            no_speech_threshold=0.6
        )
        
        # Build transcript with speaker labels
        transcript_segments = []
        full_transcript_parts = []
        
        for segment in segments:
            # Find matching speaker from diarization
            speaker_label = "Unknown"
            for diar_seg in diarized_segments:
                # Check overlap
                if (segment.start < diar_seg["end"] and 
                    segment.end > diar_seg["start"]):
                    speaker_label = diar_seg["speaker_label"]
                    break
            
            transcript_segments.append({
                "speaker_label": speaker_label,
                "start_time": segment.start,
                "end_time": segment.end,
                "text": segment.text.strip(),
                "confidence": segment.avg_logprob
            })
            
            full_transcript_parts.append(f"[{speaker_label}] {segment.text.strip()}")
        
        # Save to database
        full_transcript = "\n".join(full_transcript_parts)
        
        with get_db_context() as db:
            # Insert transcript segments
            for seg in transcript_segments:
                transcript = Transcript(
                    call_id=call_id,
                    speaker_label=seg["speaker_label"],
                    start_time=seg["start_time"],
                    end_time=seg["end_time"],
                    text=seg["text"],
                    confidence=seg["confidence"]
                )
                db.add(transcript)
            
            # Update job status
            job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if job:
                job.status = "completed"
                job.finished_at = datetime.utcnow()
                job.extra_metadata = {
                    "num_segments": len(transcript_segments),
                    "language": info.language,
                    "language_probability": info.language_probability
                }
            
            db.commit()
        
        return (call_id, full_transcript, full_transcript)
        
    except Exception as exc:
        error_msg = str(exc)
        give_up = self.request.retries >= self.max_retries
        _mark_stage_failed(call_id, job_id, error_msg, mark_call_failed=give_up)
        if give_up:
            raise
        raise self.retry(exc=exc, countdown=30)
