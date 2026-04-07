import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base, apply_migrations
from app.routers import health, chat, workflows, integrations, dashboard, webhooks, chains
from app.services.email_templates import seed_default_templates
from app.services.calendar_poller import poll_calendars
from app.services.scheduler import check_time_triggers, check_completed_appointments
from app.services.event_processor import event_worker, process_pending_events

# Import models so they register with Base.metadata before create_all
import app.models  # noqa: F401

logger = logging.getLogger(__name__)

_background_tasks = []


async def _calendar_poll_loop():
    """Poll Google Calendars every 5 minutes."""
    while True:
        try:
            await poll_calendars()
        except Exception as e:
            logger.error("Calendar poll error: %s", e)
        await asyncio.sleep(300)


async def _scheduler_loop():
    """Check time-based triggers every minute."""
    while True:
        try:
            await check_time_triggers()
            await check_completed_appointments()
        except Exception as e:
            logger.error("Scheduler error: %s", e)
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables, run migrations, seed data, start background jobs."""
    Base.metadata.create_all(bind=engine)
    apply_migrations()
    seed_default_templates()

    # Recover unprocessed events from last shutdown
    await process_pending_events()

    # Start background services
    _background_tasks.append(asyncio.create_task(_calendar_poll_loop()))
    _background_tasks.append(asyncio.create_task(_scheduler_loop()))
    _background_tasks.append(asyncio.create_task(event_worker()))

    yield

    for task in _background_tasks:
        task.cancel()


app = FastAPI(title="AImplify", version="0.4.0", lifespan=lifespan)

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
app.include_router(dashboard.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(chains.router, prefix="/api")
