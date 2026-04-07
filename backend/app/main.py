from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_URL
from app.database import engine, Base
from app.routers import health, chat, workflows

# Import models so they register with Base.metadata before create_all
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup if they don't exist."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AImplify", version="0.1.0", lifespan=lifespan)

# CORS: allow the Next.js frontend in dev and any Vercel preview deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
