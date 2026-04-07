# AImplify Backend

FastAPI backend for the AImplify AI operations platform.

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your ANTHROPIC_API_KEY
```

## Run

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Database tables are created automatically on first startup.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/chat` | Send a message and get an AI response |
| GET | `/api/conversations` | List all conversations |
| GET | `/api/conversations/{id}` | Get a conversation with messages |
| GET | `/api/workflows` | List all workflows |
