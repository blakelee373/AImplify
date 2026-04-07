# AImplify

AI operations layer for small businesses. Non-technical owners describe how their business works in plain conversation, and AImplify builds and deploys AI agents to automate their repetitive tasks across their existing tools.

## Project Structure

```
AImplify/
├── frontend/    # Next.js (TypeScript, Tailwind CSS) → deployed to Vercel
├── backend/     # FastAPI (Python, SQLAlchemy) → deployed to Railway/Render/Fly.io
└── docker-compose.yml
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run the server
uvicorn app.main:app --reload
```

The API runs at **http://localhost:8000**. Database tables are auto-created on first startup.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at **http://localhost:3000**.

### Verify Everything Works

1. Backend health check: `curl http://localhost:8000/health`
2. Open http://localhost:3000 — you should see the welcome page
3. Click "Start Chatting" to open the chat interface
4. Send a message — it should round-trip through the backend to Claude and back

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS v4 |
| Backend | FastAPI, SQLAlchemy, Python |
| Database | SQLite (swappable to PostgreSQL) |
| AI | Anthropic Claude API |

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `DATABASE_URL` | SQLAlchemy connection string (default: `sqlite:///aImplify.db`) |
| `FRONTEND_URL` | Frontend origin for CORS (default: `http://localhost:3000`) |

### Frontend

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend URL (default: `http://localhost:8000`) |
