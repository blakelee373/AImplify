import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkflowChain(Base):
    __tablename__ = "workflow_chains"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("businesses.id"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    links = relationship("WorkflowChainLink", back_populates="chain", order_by="WorkflowChainLink.position")


class WorkflowChainLink(Base):
    __tablename__ = "workflow_chain_links"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chain_id: Mapped[str] = mapped_column(String, ForeignKey("workflow_chains.id"), nullable=False)
    workflow_id: Mapped[str] = mapped_column(String, ForeignKey("workflows.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_after_previous: Mapped[int] = mapped_column(Integer, default=0)  # minutes
    condition_from_previous: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    chain = relationship("WorkflowChain", back_populates="links")
