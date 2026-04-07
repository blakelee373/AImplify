import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _generate_key() -> str:
    return uuid.uuid4().hex[:24]


class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("businesses.id"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    webhook_key: Mapped[str] = mapped_column(String, unique=True, default=_generate_key)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    field_mapping: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    receive_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
