import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base, apply_migrations
from app.routers import health, chat, workflows, integrations
from app.services.email_templates import seed_default_templates
from app.services.calendar_poller import poll_calendars

# Import models so they register with Base.metadata before create_all
import app.models  # noqa: F401

logger = logging.getLogger(__name__)

# Background task handle
_poller_task = None


async def _calendar_poll_loop():
    """Poll Google Calendars every 5 minutes."""
    while True:
        try:
            await poll_calendars()
        except Exception as e:
            logger.error("Calendar poll error: %s", e)
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables, run migrations, seed data, start background jobs."""
    global _poller_task
    Base.metadata.create_all(bind=engine)
    apply_migrations()
    seed_default_templates()

    _poller_task = asyncio.create_task(_calendar_poll_loop())
    yield
    _poller_task.cancel()


app = FastAPI(title="AImplify", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
