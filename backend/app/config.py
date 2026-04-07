import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///aImplify.db")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
