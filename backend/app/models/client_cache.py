import uuid
from datetime import datetime, timezone, date
from typing import Optional

from sqlalchemy import String, DateTime, Date, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClientCache(Base):
    __tablename__ = "client_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("businesses.id"), nullable=True)
    external_client_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_platform: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_appointments: Mapped[int] = mapped_column(Integer, default=0)
    last_appointment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
