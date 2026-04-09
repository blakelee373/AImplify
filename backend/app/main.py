import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_URL
from app.database import init_db
from app.routers import health, chat, workflows, integrations, actions, memory
from app.services.scheduler import scheduler_loop
from app.services.email_watcher import email_watcher_loop
from app.services.calendar_watcher import calendar_watcher_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    init_db()
    # Start the background scheduler for time-based triggers
    scheduler_task = asyncio.create_task(scheduler_loop())
    # Start the email watcher for event-based triggers (Gmail polling)
    email_task = asyncio.create_task(email_watcher_loop())
    # Start the calendar watcher for event-based triggers (Calendar polling)
    calendar_task = asyncio.create_task(calendar_watcher_loop())
    yield
    scheduler_task.cancel()
    email_task.cancel()
    calendar_task.cancel()


app = FastAPI(title="AImplify API", version="0.1.0", lifespan=lifespan)

# CORS — allow the Next.js frontend and any Vercel preview deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "https://*.vercel.app",
        "https://aimplify.dev",
        "https://*.aimplify.dev",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.aimplify\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(workflows.router)
app.include_router(integrations.router)
app.include_router(actions.router)
app.include_router(memory.router)
