from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base, apply_migrations
from app.routers import health, chat, workflows

# Import models so they register with Base.metadata before create_all
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup, then run migrations for any new columns."""
    Base.metadata.create_all(bind=engine)
    apply_migrations()
    yield


app = FastAPI(title="AImplify", version="0.1.0", lifespan=lifespan)

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
