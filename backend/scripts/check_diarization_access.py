"""
Verify Hugging Face token has access to pyannote diarization models.
Run: docker-compose exec api python scripts/check_diarization_access.py
"""
import os
import sys

def main():
    token = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    if not token:
        print("HF_TOKEN is not set in the environment.", file=sys.stderr)
        print("Add HF_TOKEN=your_token to .env (see https://hf.co/settings/tokens).", file=sys.stderr)
        sys.exit(1)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("huggingface_hub not installed.", file=sys.stderr)
        sys.exit(1)

    print("Checking access to pyannote/segmentation-3.0 (required for diarization)...")
    try:
        path = hf_hub_download(
            "pyannote/segmentation-3.0",
            "pytorch_model.bin",
            token=token,
        )
        print("OK: segmentation-3.0 accessible.")
    except Exception as e:
        err = str(e).lower()
        if "403" in err or "gated" in err or "authorized" in err:
            print("Access denied to pyannote/segmentation-3.0.", file=sys.stderr)
            print("", file=sys.stderr)
            print("Do this (with the same Hugging Face account that owns HF_TOKEN):", file=sys.stderr)
            print("  1. Open https://huggingface.co/pyannote/segmentation-3.0", file=sys.stderr)
            print("  2. Click 'Agree and access repository'", file=sys.stderr)
            print("  3. Open https://huggingface.co/pyannote/speaker-diarization-3.1", file=sys.stderr)
            print("  4. Click 'Agree and access repository'", file=sys.stderr)
            print("  5. Restart: docker-compose restart api", file=sys.stderr)
            sys.exit(1)
        raise

    print("Checking access to pyannote/speaker-diarization-3.1...")
    try:
        hf_hub_download(
            "pyannote/speaker-diarization-3.1",
            "config.yaml",
            token=token,
        )
        print("OK: speaker-diarization-3.1 accessible.")
    except Exception as e:
        err = str(e).lower()
        if "403" in err or "gated" in err or "authorized" in err:
            print("Access denied to pyannote/speaker-diarization-3.1.", file=sys.stderr)
            print("Accept the model terms at https://huggingface.co/pyannote/speaker-diarization-3.1", file=sys.stderr)
            sys.exit(1)
        raise

    print("Diarization access OK. You can process calls with speaker diarization.")


if __name__ == "__main__":
    main()
