"""Workflow creation and management."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.workflow import Workflow, WorkflowStep


def create_workflow_from_draft(
    db: Session,
    draft: dict,
    conversation_id: int,
    business_id: Optional[int] = None,
) -> Workflow:
    """Persist an extracted workflow draft to the database.

    The draft dict comes from the AI extraction tool and has this shape:
    {
        "name": str,
        "description": str,
        "trigger_type": str,
        "trigger_config": dict,
        "steps": [{"step_order": int, "action_type": str, "description": str, ...}]
    }
    """
    workflow = Workflow(
        name=draft.get("name", "Untitled"),
        description=draft.get("description"),
        trigger_type=draft.get("trigger_type"),
        trigger_config=draft.get("trigger_config"),
        conversation_id=conversation_id,
        business_id=business_id,
        status="draft",
    )
    db.add(workflow)
    db.flush()  # Get the workflow.id for steps

    # Compute next_run_at for scheduled workflows
    if workflow.trigger_type == "schedule":
        trigger_config = draft.get("trigger_config") or {}
        cron_expr = trigger_config.get("cron_expression")
        if cron_expr:
            from app.services.scheduler import compute_next_run
            workflow.next_run_at = compute_next_run(
                cron_expr, tz_name=trigger_config.get("timezone", "UTC")
            )

    # Set last_run_at for event-triggered workflows (polling window start)
    if workflow.trigger_type == "event":
        from datetime import datetime, timezone
        workflow.last_run_at = datetime.now(timezone.utc)

    for step_data in draft.get("steps", []):
        step = WorkflowStep(
            workflow_id=workflow.id,
            step_order=step_data.get("step_order", 0),
            action_type=step_data.get("action_type", "unknown"),
            action_config=step_data.get("action_config"),
            description=step_data.get("description"),
        )
        db.add(step)

    db.commit()
    db.refresh(workflow)
    return workflow
