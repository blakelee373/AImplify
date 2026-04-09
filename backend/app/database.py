from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

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


_MIGRATIONS = [
    "ALTER TABLE workflows ADD COLUMN conversation_id INTEGER REFERENCES conversations(id)",
    "ALTER TABLE workflows ADD COLUMN next_run_at TIMESTAMP",
    "ALTER TABLE workflows ADD COLUMN last_run_at TIMESTAMP",
]


def init_db():
    """Create all tables if they don't exist, then run migrations."""
    from app.models import user, business, conversation, workflow, activity_log, integration, action_form  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Run pending migrations (skip if column already exists)
    with engine.connect() as conn:
        for sql in _MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()
