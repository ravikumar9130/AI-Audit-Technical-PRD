"""
Bootstrap: run before any other worker code so torch.load uses weights_only=False
by default (required for pyannote/SpeechBrain checkpoints on PyTorch 2.6+).
Must be imported first in celery_app.py.
"""
import os

os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")

import torch

_orig_torch_load = torch.load


def _safe_torch_load(*args, **kwargs):
    if "weights_only" not in kwargs:
        kwargs["weights_only"] = False
    return _orig_torch_load(*args, **kwargs)


def apply_patch():
    torch.load = _safe_torch_load
    if hasattr(torch, "serialization") and hasattr(torch.serialization, "load"):
        torch.serialization.load = _safe_torch_load


torch.load = _safe_torch_load
if hasattr(torch, "serialization") and hasattr(torch.serialization, "load"):
    torch.serialization.load = _safe_torch_load
