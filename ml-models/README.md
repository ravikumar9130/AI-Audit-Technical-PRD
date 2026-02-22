# ML models directory

The pipeline expects the LLM model for the scoring stage at:

**`llama-3-8b-instruct-q4.gguf`**

Download it once (e.g. after first `docker-compose up`):

```bash
docker-compose exec api python scripts/download_llm_model.py
```

This fetches the Q4 GGUF from Hugging Face (~5 GB) into this directory. If the model is gated, accept the license on the repo page and run `huggingface-cli login` before the script.

Without this file, uploads can run through normalize → VAD → diarization → transcription but the scoring step will fail.
