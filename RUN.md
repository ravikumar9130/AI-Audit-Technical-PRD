# How to Run Audit AI

## 1. Start all services

From the project root:

```bash
cd audit-ai
docker-compose up -d --build
```

Wait ~30–60 seconds for the API and frontend to be ready.

## 2. (First time only) Database, admin user, and LLM model

```bash
# Run migrations (creates alembic version table)
docker-compose exec api alembic upgrade head

# Create admin user (run once; use these credentials to log in)
docker-compose exec api python scripts/create_admin.py

# Download LLM model for scoring (~5 GB, run once)
docker-compose exec api python scripts/download_llm_model.py
```

If `create_admin.py` is missing, create an admin manually via the API or DB.  
The model is written to `./ml-models/llama-3-8b-instruct-q4.gguf`. For gated Hugging Face models, accept the license and run `huggingface-cli login` first.

**Speaker diarization (pyannote):** Set `HF_TOKEN` in `.env` to a [Hugging Face token](https://hf.co/settings/tokens). You must accept the user conditions for both [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) and [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) (open each link while logged in and click “Agree and access repository”). Then run:

```bash
docker-compose exec api python scripts/check_diarization_access.py
```

If that script reports “Access denied”, complete the steps it prints and restart the API.

## 3. Open the app

| What        | URL                      |
|------------|---------------------------|
| **Frontend** | http://localhost:3000    |
| **API docs** | http://localhost:8000/docs |
| **API health** | http://localhost:8000/health |

## 4. Check that services are up

```bash
docker-compose ps
```

All of `frontend`, `api`, `postgres`, `redis`, `minio` should be **Up**. The API container also runs the Celery worker (processes uploads). Then:

```bash
curl -s http://localhost:8000/health
# Should return: {"status":"healthy", ...}
```

If the site still doesn’t load (connection reset / ERR_CONNECTION_*):

- Wait 1–2 minutes and try again.
- Check logs: `docker-compose logs api frontend`
- Restart: `docker-compose restart api frontend`

---

## Optional: .env (you don’t have to touch it)

Everything works with defaults. To override (e.g. for production), copy and edit:

```bash
cp .env.example .env
```

**Only variable you might want to set:**

| Variable   | Required for run? | Default / note |
|-----------|--------------------|----------------|
| `JWT_SECRET` | No (compose sets a default) | Must be **≥ 32 characters** if you set it in `.env`. |

Compose already sets:

- `DATABASE_URL`, `REDIS_URL`, MinIO, `JWT_SECRET` (long enough default), `LLM_MODEL_PATH`

So **no .env or creds are required** for a normal `docker-compose up` run.

---

## If something fails

1. **Frontend: “connection reset” / “can’t be reached”**  
   - Ensure API is healthy: `curl http://localhost:8000/health`  
   - Restart: `docker-compose restart api frontend`

2. **API won’t start (e.g. import / config error)**  
   - Check: `docker-compose logs api`  
   - Ensure no volume is overwriting the `models` package (we use `./ml-models:/app/ml-models`).

3. **Login fails (401 / invalid credentials)**  
   - Run: `docker-compose exec api python scripts/create_admin.py`  
   - Use the email/password it prints.

4. **Uploads stay "queued"**  
   The API container runs both the API and the Celery worker. If calls stay queued, restart the API: `docker-compose restart api` and check logs: `docker-compose logs -f api`. Ensure `./ml-models/llama-3-8b-instruct-q4.gguf` exists for the scoring step. First run may take a few minutes while the worker starts.

5. **Call stuck in "processing" for hours**  
   On CPU-only setups, the LLM step uses a lower token limit (`LLM_MAX_TOKENS_CPU=768`) so 1–2 min calls finish in a few minutes instead of 10+. Pipeline stages have time limits (scoring 15–20 min, transcription 10–15 min, diarization 8–12 min).  
   - **Check where it’s stuck:** `docker-compose logs api 2>&1 | grep -E "scoring|diariz|transcri|normalize|run_vad"` — you’ll see which stage last succeeded. If you see `[scoring] call_id=X loading LLM` but no `LLM response received`, the worker is still running the model (can take 3–8 min on CPU) or it crashed.  
   - **Mark stuck calls failed and re-upload:** After a code/restart change, in-flight chains can be lost; those calls stay "processing". Mark them failed, then re-upload the file:
   ```bash
   docker-compose exec api python scripts/mark_stuck_calls_failed.py --hours 0.5
   docker-compose restart api
   ```
   Then upload the call again. Use `--hours 0.5` to mark anything stuck over 30 min; or `--hours 2` for 2+ hours.

6. **Clear all recent calls (dev only)**  
   To reset the dashboard and remove all calls from the DB (and optionally from storage):
   ```bash
   docker-compose exec api python scripts/clear_all_calls.py
   ```
   To only delete call records and leave files in MinIO/S3:
   ```bash
   docker-compose exec api python scripts/clear_all_calls.py --db-only
   ```

7. **Clean restart**  
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```
