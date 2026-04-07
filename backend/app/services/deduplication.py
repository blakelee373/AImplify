"""Prevent duplicate workflow executions for the same trigger event."""

import logging
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.workflow_execution import WorkflowExecution

logger = logging.getLogger(__name__)

# Default cooldown: don't re-fire the same workflow for the same client within 60 min
DEFAULT_COOLDOWN_MINUTES = 60


def is_duplicate(
    workflow_id: str,
    trigger_event_id: str,
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
) -> bool:
    """Return True if this (workflow, trigger_event) was already executed recently."""
    db = SessionLocal()
    try:
        # Exact event match
        exact = (
            db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.trigger_event_id == trigger_event_id,
                WorkflowExecution.status.in_(["completed", "running", "dry_run"]),
            )
            .first()
        )
        if exact:
            return True

        # Cooldown check: any execution within the cooldown window?
        if cooldown_minutes > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
            recent = (
                db.query(WorkflowExecution)
                .filter(
                    WorkflowExecution.workflow_id == workflow_id,
                    WorkflowExecution.started_at >= cutoff,
                    WorkflowExecution.status.in_(["completed", "running"]),
                )
                .first()
            )
            if recent:
                return True

        return False
    finally:
        db.close()


def record_execution(workflow_id: str, trigger_event_id: str):
    """Note that this combination has been processed (for dedup lookups)."""
    # The WorkflowExecution record is already created by the executor,
    # so this is mainly a logging hook for future use.
    logger.debug("Recorded execution: workflow=%s event=%s", workflow_id, trigger_event_id)
