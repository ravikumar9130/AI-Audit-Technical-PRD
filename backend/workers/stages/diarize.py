"""
Speaker diarization stage using Pyannote Audio.
"""
import os
from collections import namedtuple
from datetime import datetime
from typing import Tuple, List, Dict, Any

import torch
_orig_torch_load = torch.load
def _torch_load_safe(*args, **kwargs):
    if "weights_only" not in kwargs:
        kwargs["weights_only"] = False
    return _orig_torch_load(*args, **kwargs)
torch.load = _torch_load_safe
if hasattr(torch.serialization, "load"):
    torch.serialization.load = _torch_load_safe

import torchaudio

try:
    from huggingface_hub import hf_hub_download as _orig_hf_hub_download
    def _hf_hub_download_compat(*args, use_auth_token=None, **kwargs):
        kwargs.pop("use_auth_token", None)
        if use_auth_token is not None:
            kwargs["token"] = use_auth_token
        return _orig_hf_hub_download(*args, **kwargs)
    import huggingface_hub.file_download as _hf_fd
    import huggingface_hub as _hf
    _hf_fd.hf_hub_download = _hf_hub_download_compat
    _hf.hf_hub_download = _hf_hub_download_compat
except Exception:
    pass

if not hasattr(torchaudio, "AudioMetaData"):
    _AudioMetaData = namedtuple(
        "AudioMetaData",
        ["sample_rate", "num_frames", "num_channels", "bits_per_sample", "encoding"],
        defaults=(0, "PCM_F"),
    )
    torchaudio.AudioMetaData = _AudioMetaData

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

# Global diarization pipeline (loaded once per worker)
_diarization_pipeline = None

def get_diarization_pipeline():
    """Get or load diarization pipeline."""
    global _diarization_pipeline
    if _diarization_pipeline is None:
        hf_token = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
        if not hf_token:
            raise RuntimeError(
                "Diarization requires HF_TOKEN in .env. Create a token at https://hf.co/settings/tokens and "
                "accept terms at https://huggingface.co/pyannote/speaker-diarization-3.1 and "
                "https://huggingface.co/pyannote/segmentation-3.0"
            )
        try:
            from huggingface_hub import login as hf_login
            hf_login(token=hf_token)
        except Exception:
            pass
        try:
            from pyannote.audio import Pipeline

            try:
                _diarization_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=hf_token,
                )
            except TypeError as e:
                if "unexpected keyword argument" in str(e) and "token" in str(e):
                    _diarization_pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        token=hf_token,
                    )
                else:
                    raise
            if _diarization_pipeline is None:
                raise RuntimeError(
                    "Could not load diarization pipeline (403). Accept model terms at "
                    "https://huggingface.co/pyannote/speaker-diarization-3.1 and "
                    "https://huggingface.co/pyannote/segmentation-3.0 (required)"
                )
            if torch.cuda.is_available():
                _diarization_pipeline.to(torch.device("cuda"))

        except AttributeError as e:
            if "NoneType" in str(e) and "eval" in str(e):
                raise RuntimeError(
                    "Diarization requires accepting Hugging Face model terms. Open these links (logged in with the account that owns HF_TOKEN), "
                    "then click 'Agree and access repository' on each: "
                    "1) https://huggingface.co/pyannote/segmentation-3.0 "
                    "2) https://huggingface.co/pyannote/speaker-diarization-3.1"
                ) from e
            raise
        except Exception as e:
            err = str(e).lower()
            if "weights only" in err or "unpicklingerror" in err or "weights_only" in err:
                raise RuntimeError(
                    "Diarization model load failed (PyTorch weights_only). This is fixed in the latest code; restart the API container."
                ) from e
            if "403" in err or "forbidden" in err or "gated" in err or "could not download" in err or "authorized list" in err or "gatedrepoerror" in err:
                raise RuntimeError(
                    "Diarization model access denied. You must accept the user conditions on Hugging Face (same account as HF_TOKEN): "
                    "1) https://huggingface.co/pyannote/segmentation-3.0 "
                    "2) https://huggingface.co/pyannote/speaker-diarization-3.1"
                ) from e
            print(f"Failed to load diarization pipeline: {e}")
            raise

    return _diarization_pipeline


DIARIZE_SOFT_TIME_LIMIT = 8 * 60
DIARIZE_TIME_LIMIT = 12 * 60

@celery_app.task(bind=True, max_retries=3, soft_time_limit=DIARIZE_SOFT_TIME_LIMIT, time_limit=DIARIZE_TIME_LIMIT)
def run_diarization_task(self, previous_result: Tuple[int, str, List[Dict]], call_id: int, work_dir: str) -> Tuple[int, str, List[Dict]]:
    """
    Run speaker diarization on audio segments.
    
    Args:
        previous_result: Tuple of (call_id, audio_path, speech_segments) from VAD
        
    Returns:
        Tuple of (call_id, audio_path, diarized_segments)
    """
    _, audio_path, speech_segments = previous_result
    job_id = None
    
    try:
        # Log stage start
        with get_db_context() as db:
            job = ProcessingJob(
                call_id=call_id,
                stage="diarization",
                status="in_progress",
                celery_task_id=self.request.id,
                started_at=datetime.utcnow()
            )
            db.add(job)
            db.commit()
            job_id = job.job_id
        
        pipeline = get_diarization_pipeline()
        if pipeline is None:
            raise RuntimeError(
                "Diarization pipeline failed to load. Set HF_TOKEN and accept model terms at "
                "https://huggingface.co/pyannote/speaker-diarization-3.1"
            )
        diarization = pipeline(audio_path)
        
        # Extract speaker segments
        speaker_segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speaker_segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
        
        # Assign speaker labels (Agent/Customer)
        # Heuristic: First speaker is usually Agent
        unique_speakers = list(set(seg["speaker"] for seg in speaker_segments))
        speaker_mapping = {}
        
        if len(unique_speakers) >= 1:
            speaker_mapping[unique_speakers[0]] = "Agent"
        if len(unique_speakers) >= 2:
            speaker_mapping[unique_speakers[1]] = "Customer"
        if len(unique_speakers) > 2:
            for i, speaker in enumerate(unique_speakers[2:], 2):
                speaker_mapping[speaker] = f"Speaker_{i}"
        
        # Map segments
        diarized_segments = []
        for seg in speaker_segments:
            diarized_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "speaker_label": speaker_mapping.get(seg["speaker"], seg["speaker"]),
                "speaker_id": seg["speaker"]
            })
        
        # Update job status
        with get_db_context() as db:
            job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if job:
                job.status = "completed"
                job.finished_at = datetime.utcnow()
                job.extra_metadata = {
                    "num_speakers": len(unique_speakers),
                    "num_segments": len(diarized_segments),
                    "speaker_mapping": speaker_mapping
                }
                db.commit()
        
        return (call_id, audio_path, diarized_segments)
        
    except Exception as exc:
        error_msg = str(exc)
        give_up = self.request.retries >= self.max_retries
        _mark_stage_failed(call_id, job_id, error_msg, mark_call_failed=give_up)
        if give_up:
            raise
        raise self.retry(exc=exc, countdown=30)
