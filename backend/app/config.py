import os
from dotenv import load_dotenv

# Load .env from the project root (one level above backend/)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///aImplify.db")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
