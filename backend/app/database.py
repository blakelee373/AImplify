import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

# check_same_thread=False is required for SQLite with FastAPI's threaded request handling
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after initial schema — each entry is an ALTER TABLE statement.
# Failed statements (column already exists) are silently skipped.
_MIGRATIONS = [
    # Phase 1
    "ALTER TABLE conversations ADD COLUMN workflow_id VARCHAR REFERENCES workflows(id)",
    "ALTER TABLE workflows ADD COLUMN deleted_at DATETIME",
    "ALTER TABLE workflows ADD COLUMN trigger_description TEXT",
    "ALTER TABLE workflows ADD COLUMN conditions JSON",
]


def apply_migrations():
    """Add new columns to existing tables. Safe to run repeatedly."""
    with engine.connect() as conn:
        for sql in _MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()
