# AImplify - Project Instructions

## Product
AI operations layer for medspas. Owners describe how their business works in plain conversation, and AImplify builds AI agents to automate repetitive tasks.

## Tech Stack
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI, SQLAlchemy, SQLite
- **AI:** Anthropic Claude API
- **Deployment:** Vercel (frontend), Cloudflare tunnel (backend during dev)

## Python Compatibility
- Target Python 3.9 — use `Optional[str]` not `str | None`, `List[str]` not `list[str]`, `timezone.utc` not `datetime.UTC`

## Phase Response Requirements
- At the end of EVERY phase response, provide a bullet-pointed list in layman's terms of the physical changes the user should see in the Vercel deployment. Example format:

### What you'll see on the deployment:
- The chat page now shows a text box and send button
- Messages you type appear on screen with AI responses below them
- A new "Dashboard" link appears in the sidebar
