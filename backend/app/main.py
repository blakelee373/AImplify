from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_URL
from app.database import init_db
from app.routers import health, chat, workflows, integrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    init_db()
    yield


app = FastAPI(title="AImplify API", version="0.1.0", lifespan=lifespan)

# CORS — allow the Next.js frontend and any Vercel preview deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "https://*.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(workflows.router)
app.include_router(integrations.router)
