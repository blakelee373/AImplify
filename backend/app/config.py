import os
from dotenv import load_dotenv

# Load .env from the project root (one level above backend/)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///aImplify.db")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Token encryption
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
