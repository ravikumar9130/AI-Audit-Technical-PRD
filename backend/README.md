# Backend

FastAPI backend with Celery workers for ML pipeline processing.

## Structure

- `api/` - REST API endpoints
- `core/` - Configuration, security, database
- `models/` - SQLAlchemy ORM models
- `services/` - Business logic (storage, websockets)
- `workers/` - Celery tasks and ML pipeline stages
- `prompts/` - LLM prompt templates for scoring

## Development

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run API
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker
celery -A workers.celery_app worker --loglevel=info --pool=prefork

# Run Celery beat (for scheduled tasks)
celery -A workers.celery_app beat --loglevel=info
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - JWT login
- `POST /api/auth/refresh` - Refresh token

### Upload
- `POST /api/upload` - Upload audio file
- `POST /api/upload/bulk` - Bulk ZIP upload

### Calls
- `GET /api/calls` - List calls (RBAC filtered)
- `GET /api/calls/{call_id}` - Get call details
- `GET /api/calls/{call_id}/transcript` - Get transcript
- `GET /api/calls/{call_id}/results` - Get evaluation results

### Dashboard
- `GET /api/dashboard` - Role-based dashboard data

### Templates
- `GET /api/templates` - List scoring templates
- `POST /api/templates` - Create template (Manager+)

### WebSocket
- `WS /ws/notifications` - Real-time updates
