"""Workflow runner — execute all steps in a workflow sequentially."""

from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.workflow import Workflow
from app.models.activity_log import ActivityLog
from app.services.step_executor import execute_step


async def run_workflow(
    db: Session,
    workflow: Workflow,
    context: Dict,
) -> List[dict]:
    """Run every step in the workflow in order.

    context: runtime data like {"client_name": "Jane", "client_email": "jane@example.com"}
    Returns a list of step results.
    """
    # Ensure timezone is always in context — pull from trigger_config if missing
    if "timezone" not in context:
        wf_tz = (workflow.trigger_config or {}).get("timezone")
        if wf_tz:
            context["timezone"] = wf_tz

    # Ensure owner_email is in context so "send to myself" resolves correctly
    if "owner_email" not in context:
        try:
            from app.services.google_auth import get_google_credentials
            from googleapiclient.discovery import build as goog_build

            creds = get_google_credentials(db, provider="gmail")
            if creds:
                service = goog_build("gmail", "v1", credentials=creds)
                profile = service.users().getProfile(userId="me").execute()
                email = profile.get("emailAddress")
                if email:
                    context["owner_email"] = email
                    if "client_email" not in context:
                        context["client_email"] = email
        except Exception:
            pass

    results = []

    for step in workflow.steps:
        result = await execute_step(
            db=db,
            action_type=step.action_type,
            step_description=step.description or step.action_type,
            workflow_name=workflow.name,
            action_config=step.action_config,
            context=context,
        )

        # Log each step execution
        log = ActivityLog(
            workflow_id=workflow.id,
            action_type=step.action_type,
            description=f"Step {step.step_order}: {step.description or step.action_type}",
            details={
                "step_order": step.step_order,
                "status": result["status"],
                "result": result["details"],
                "context_keys": list(context.keys()),
            },
        )
        db.add(log)
        db.commit()

        results.append({
            "step_order": step.step_order,
            "action_type": step.action_type,
            "description": step.description,
            **result,
        })

        # Stop on first error
        if result["status"] == "error":
            break

    return results
