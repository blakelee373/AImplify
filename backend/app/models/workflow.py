from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import String, ForeignKey, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[Optional[int]] = mapped_column(ForeignKey("businesses.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, testing, active, paused
    trigger_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    trigger_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    business: Mapped[Optional["Business"]] = relationship(back_populates="workflows")
    steps: Mapped[List["WorkflowStep"]] = relationship(
        back_populates="workflow", order_by="WorkflowStep.step_order"
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"))
    step_order: Mapped[int] = mapped_column(Integer)
    action_type: Mapped[str] = mapped_column(String(100))
    action_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="steps")
