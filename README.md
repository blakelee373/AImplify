# AImplify

AI operations layer for small businesses. Describe how your business works in plain conversation, and AImplify builds AI agents to handle your repetitive tasks.

## Tech Stack

- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS v4
- **Backend:** Python, FastAPI, SQLAlchemy, SQLite
- **AI:** Anthropic Claude API
- **Deployment:** Vercel (frontend), TBD (backend)

## Getting Started

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. Hit `/health` to verify.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`.

### Environment Variables

Copy the `.env.example` in `backend/` and fill in your keys:

```
ANTHROPIC_API_KEY=your-key-here
DATABASE_URL=sqlite:///aImplify.db
FRONTEND_URL=http://localhost:3000
```

The frontend uses `NEXT_PUBLIC_API_URL` to point to the backend (defaults to `http://localhost:8000`).

## Project Structure

```
AImplify/
├── frontend/          # Next.js app (Vercel)
│   ├── src/app/       # App Router pages
│   ├── src/components/# UI components
│   └── src/lib/       # API client, utilities
├── backend/           # FastAPI app
│   ├── app/models/    # SQLAlchemy models
│   ├── app/routers/   # API endpoints
│   ├── app/services/  # Business logic (AI engine, workflows)
│   └── app/integrations/ # Third-party connectors
└── CLAUDE.md          # AI assistant instructions
```
