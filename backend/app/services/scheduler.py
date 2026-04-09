"""Background scheduler — fires time-based workflows on their cron schedule."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from croniter import croniter

logger = logging.getLogger(__name__)


def compute_next_run(
    cron_expr: str, after: Optional[datetime] = None, tz_name: str = "UTC"
) -> Optional[datetime]:
    """Compute the next fire time (in UTC) for a cron expression.

    cron_expr: standard 5-field cron (minute hour dom month dow)
    after: base time in UTC; defaults to now
    tz_name: the IANA timezone the schedule is written in (e.g. "America/Chicago")
    """
    from zoneinfo import ZoneInfo

    if not cron_expr or not croniter.is_valid(cron_expr):
        return None

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    if after is None:
        after = datetime.now(timezone.utc)

    # Convert to the schedule's local timezone for correct cron matching
    local_now = after.astimezone(tz)
    cron = croniter(cron_expr, local_now)
    next_local = cron.get_next(datetime)

    # Convert back to UTC for storage
    return next_local.astimezone(timezone.utc)


def update_next_run(db, workflow) -> None:
    """Recompute and persist next_run_at for a workflow."""
    trigger_config = workflow.trigger_config or {}
    cron_expr = trigger_config.get("cron_expression")
    tz_name = trigger_config.get("timezone", "UTC")

    if cron_expr and workflow.trigger_type == "schedule":
        workflow.next_run_at = compute_next_run(cron_expr, tz_name=tz_name)
    else:
        workflow.next_run_at = None


async def scheduler_loop() -> None:
    """Background task that checks for due workflows every 60 seconds."""
    from app.database import SessionLocal
    from app.models.workflow import Workflow
    from app.models.activity_log import ActivityLog
    from app.services.workflow_runner import run_workflow

    # Brief startup delay to let the app finish initializing
    await asyncio.sleep(5)
    logger.info("Scheduler started")

    while True:
        try:
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)

                # Find all active scheduled workflows that are due
                due_workflows = (
                    db.query(Workflow)
                    .filter(
                        Workflow.trigger_type == "schedule",
                        Workflow.status == "active",
                        Workflow.next_run_at != None,  # noqa: E711
                        Workflow.next_run_at <= now,
                    )
                    .all()
                )

                for workflow in due_workflows:
                    logger.info(
                        "Scheduler firing workflow %d (%s)",
                        workflow.id,
                        workflow.name,
                    )
                    try:
                        context = {}  # Scheduled runs have no runtime context
                        results = await run_workflow(db, workflow, context)
                        all_success = all(r["status"] == "success" for r in results)

                        # Log the scheduled execution
                        log = ActivityLog(
                            workflow_id=workflow.id,
                            action_type="scheduled_run",
                            description=f"Scheduled run of '{workflow.name}' — "
                            + ("all steps succeeded" if all_success else "some steps failed"),
                            details={
                                "trigger": "scheduler",
                                "steps_executed": len(results),
                                "all_success": all_success,
                            },
                        )
                        db.add(log)

                    except Exception as exc:
                        logger.exception(
                            "Scheduler error running workflow %d: %s",
                            workflow.id,
                            exc,
                        )
                        log = ActivityLog(
                            workflow_id=workflow.id,
                            action_type="scheduled_run",
                            description=f"Scheduled run of '{workflow.name}' failed: {exc}",
                            details={"trigger": "scheduler", "error": str(exc)},
                        )
                        db.add(log)

                    # Always advance: set last_run_at and recompute next_run_at
                    try:
                        workflow.last_run_at = now
                        workflow.updated_at = now
                        update_next_run(db, workflow)
                        db.commit()
                    except Exception as adv_exc:
                        logger.exception(
                            "Scheduler failed to advance workflow %d: %s",
                            workflow.id,
                            adv_exc,
                        )
                        db.rollback()

            finally:
                db.close()

        except Exception as exc:
            logger.exception("Scheduler loop error: %s", exc)

        await asyncio.sleep(60)
