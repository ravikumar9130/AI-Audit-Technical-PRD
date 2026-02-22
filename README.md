# Audit AI – Enterprise Speech Intelligence Platform

An enterprise-grade platform for automating call QA and compliance audits using local ML models.

---

## Demo

**Watch the demo video:** [audit-ai-demo.mp4 (Google Drive)](https://drive.google.com/file/d/1KqasUYzBEYpJw_UW8xpGrVHEuPdevuwr/view?usp=sharing)

---

## Screenshots

| Dashboard | Call detail | Upload |
|-----------|-------------|--------|
| *(Add `docs/screenshots/dashboard.png`)* | *(Add `docs/screenshots/call-detail.png`)* | *(Add `docs/screenshots/upload.png`)* |

Add your screenshots under `docs/screenshots/` and reference them here, for example:

```markdown
![Dashboard](docs/screenshots/dashboard.png)
![Call detail](docs/screenshots/call-detail.png)
![Upload](docs/screenshots/upload.png)
```

---

## Architecture

- **Frontend**: Next.js 14 + TailwindCSS + ShadCN
- **API**: FastAPI + Uvicorn
- **Workers**: Celery + Redis + GPU-accelerated ML pipeline
- **Database**: PostgreSQL + JSONB
- **Storage**: MinIO (S3-compatible)
- **LLM**: vLLM with Llama-3-8B/Mistral-7B (quantized)

## Quick Start

```bash
# Clone and enter directory
cd audit-ai

# Start core services (frontend, API, Postgres, Redis, MinIO). On Mac / without GPU this is the default.
docker-compose up -d --build

# Optional: start GPU worker + beat (Linux with NVIDIA only)
# docker-compose --profile gpu up -d --build

# Run database migrations
docker-compose exec api alembic upgrade head

# Create initial admin user
docker-compose exec api python scripts/create_admin.py

# Access services
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

**Note:** Worker and Beat (Celery ML pipeline) are under the `gpu` profile and require an NVIDIA GPU. Omit `--profile gpu` on Mac or when you only need the app UI and API.

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=postgresql://auditai:auditai@postgres:5432/auditai

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=auditai-calls

# JWT
JWT_SECRET=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# LLM
LLM_MODEL_PATH=/app/models/llama-3-8b-instruct-q4.gguf
VLLM_GPU_MEMORY_UTILIZATION=0.85
```

## ML Pipeline Stages

1. Audio Standardization (FFmpeg)
2. Voice Activity Detection (Silero VAD)
3. Overlap Detection (Optional - Conv-TasNet)
4. Speaker Diarization (Pyannote)
5. ASR Transcription (Faster-Whisper)
6. Emotion/Gender Classification (Optional)
7. LLM Scoring & Extraction
8. Result Storage
9. Notification (WebSocket)

## Security

- TLS 1.3 for all traffic
- JWT authentication with RBAC
- AES-256 encryption at rest
- PII redaction in transcripts
- SOC2-grade audit logging
- GDPR/CCPA compliance with automated retention

## Deployment

### Local Development
```bash
docker-compose up -d
```

### Production (Kubernetes)
```bash
cd kubernetes/helm-charts
helm install audit-ai ./audit-ai
```

## License

Enterprise - All rights reserved.
