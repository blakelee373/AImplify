from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BusinessMemory(Base):
    __tablename__ = "business_memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("businesses.id"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(100), default="general")
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="chat")
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
