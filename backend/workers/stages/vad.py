"""
Voice Activity Detection stage using Silero VAD.
"""
import os
import torch
import torchaudio
import soundfile as sf
from datetime import datetime
from typing import Tuple, List, Dict, Any

from workers.celery_app import celery_app
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

# Global VAD model (loaded once per worker)
_vad_model = None

def get_vad_model():
    """Get or load VAD model."""
    global _vad_model
    if _vad_model is None:
        try:
            # Load Silero VAD
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            _vad_model = model
        except Exception as e:
            print(f"Failed to load VAD model: {e}")
            raise
    return _vad_model


@celery_app.task(bind=True, max_retries=3)
def run_vad_task(self, previous_result: Tuple[int, str], call_id: int, work_dir: str) -> Tuple[int, str, List[Dict[str, Any]]]:
    """
    Run Voice Activity Detection on normalized audio.
    
    Args:
        previous_result: Tuple of (call_id, audio_path) from normalization
        
    Returns:
        Tuple of (call_id, audio_path, speech_segments)
    """
    _, audio_path = previous_result
    job_id = None
    
    try:
        # Log stage start
        with get_db_context() as db:
            job = ProcessingJob(
                call_id=call_id,
                stage="vad",
                status="in_progress",
                celery_task_id=self.request.id,
                started_at=datetime.utcnow()
            )
            db.add(job)
            db.commit()
            job_id = job.job_id
        
        # Load audio (soundfile avoids torchcodec dependency; input is always normalized WAV)
        data, sample_rate = sf.read(audio_path, dtype="float32")
        if data.ndim == 1:
            data = data.reshape(1, -1)
        else:
            data = data.T
        waveform = torch.from_numpy(data.copy())

        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(sample_rate, 16000)
            waveform = resampler(waveform)
            sample_rate = 16000
        
        # Get VAD model
        model = get_vad_model()
        
        # Run VAD
        speech_timestamps = []
        
        # Process in chunks
        window_size_samples = 512  # 32ms at 16kHz
        
        with torch.no_grad():
            for i in range(0, waveform.shape[1], window_size_samples):
                chunk = waveform[:, i:i + window_size_samples]
                if chunk.shape[1] < window_size_samples:
                    # Pad last chunk
                    chunk = torch.nn.functional.pad(chunk, (0, window_size_samples - chunk.shape[1]))
                
                speech_prob = model(chunk, sample_rate).item()
                
                if speech_prob > settings.VAD_CONFIDENCE_THRESHOLD:
                    start_time = i / sample_rate
                    end_time = (i + window_size_samples) / sample_rate
                    
                    # Merge with previous segment if close
                    if speech_timestamps and start_time - speech_timestamps[-1]["end"] < 0.5:
                        speech_timestamps[-1]["end"] = end_time
                    else:
                        speech_timestamps.append({
                            "start": start_time,
                            "end": end_time,
                            "confidence": speech_prob
                        })
        
        # Apply hangover (padding)
        hangover_sec = settings.VAD_HANGOVER_MS / 1000.0
        total_duration = waveform.shape[1] / sample_rate
        
        padded_segments = []
        for seg in speech_timestamps:
            padded_segments.append({
                "start": max(0, seg["start"] - hangover_sec),
                "end": min(total_duration, seg["end"] + hangover_sec),
                "confidence": seg["confidence"]
            })
        
        # Calculate speech ratio
        speech_duration = sum(seg["end"] - seg["start"] for seg in padded_segments)
        speech_ratio = speech_duration / total_duration if total_duration > 0 else 0
        
        # Update job status
        with get_db_context() as db:
            job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if job:
                job.status = "completed"
                job.finished_at = datetime.utcnow()
                job.extra_metadata = {
                    "num_segments": len(padded_segments),
                    "speech_ratio": speech_ratio,
                    "total_duration": total_duration,
                    "speech_duration": speech_duration
                }
                db.commit()
        
        return (call_id, audio_path, padded_segments)
        
    except Exception as exc:
        error_msg = str(exc)
        give_up = self.request.retries >= self.max_retries
        _mark_stage_failed(call_id, job_id, error_msg, mark_call_failed=give_up)
        if give_up:
            raise
        raise self.retry(exc=exc, countdown=30)
