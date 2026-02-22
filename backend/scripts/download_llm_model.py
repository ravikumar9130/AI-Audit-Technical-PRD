"""
Download the LLM model (Llama 3 8B Instruct Q4 GGUF) for the scoring stage.
Run once to populate ml-models/ so the worker can complete the pipeline.

  docker-compose exec api python scripts/download_llm_model.py

Or from project root with backend venv:
  cd backend && python scripts/download_llm_model.py
  (set LLM_MODEL_PATH=../ml-models/llama-3-8b-instruct-q4.gguf if needed)

For gated models on Hugging Face, log in first:
  huggingface-cli login
or set HF_TOKEN in the environment.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Default path used by docker-compose and backend config
DEFAULT_PATH = "/app/ml-models/llama-3-8b-instruct-q4.gguf"
REPO_ID = "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF"
FILE_NAME = "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"


def main():
    out_path = os.environ.get("LLM_MODEL_PATH", DEFAULT_PATH)
    if not os.path.isabs(out_path):
        out_path = os.path.abspath(out_path)
    out_dir = os.path.dirname(out_path)
    os.makedirs(out_dir, exist_ok=True)

    if os.path.isfile(out_path):
        print(f"Model already exists: {out_path}")
        return

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Install huggingface_hub: pip install huggingface_hub")
        sys.exit(1)

    print(f"Downloading {REPO_ID} ({FILE_NAME}) to {out_path} ...")
    print("(This may take a while; file is ~5 GB.)")
    try:
        downloaded = hf_hub_download(
            repo_id=REPO_ID,
            filename=FILE_NAME,
            local_dir=out_dir,
            local_dir_use_symlinks=False,
        )
        # App expects llama-3-8b-instruct-q4.gguf
        if os.path.normpath(downloaded) != os.path.normpath(out_path):
            os.rename(downloaded, out_path)
            print(f"Saved as {out_path}")
        else:
            print(f"Saved to {out_path}")
    except Exception as e:
        print(f"Download failed: {e}")
        if "401" in str(e) or "403" in str(e) or "gated" in str(e).lower():
            print("This model may be gated. Accept the license at:")
            print(f"  https://huggingface.co/{REPO_ID}")
            print("Then run: huggingface-cli login")
        sys.exit(1)


if __name__ == "__main__":
    main()
