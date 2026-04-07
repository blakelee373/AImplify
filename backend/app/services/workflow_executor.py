"""Execute workflow steps in order — either live or as a dry run."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.database import SessionLocal
from app.models.workflow import Workflow, WorkflowStep
from app.models.workflow_execution import WorkflowExecution
from app.models.activity_log import ActivityLog
from app.services.action_router import route_action
from app.services.variable_resolver import resolve_variables

logger = logging.getLogger(__name__)


async def execute_workflow(
    workflow_id: str,
    trigger_context: Dict[str, Any],
    dry_run: bool = False,
    trigger_event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all steps of a workflow in order.

    If *dry_run* is True, steps are resolved but not actually executed.
    Returns an execution report with per-step results.
    """
    db = SessionLocal()
    try:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            return {"success": False, "error": "Workflow not found"}

        if not dry_run and workflow.status not in ("active", "testing"):
            return {"success": False, "error": "Workflow is not active (status={})".format(workflow.status)}

        steps = (
            db.query(WorkflowStep)
            .filter(WorkflowStep.workflow_id == workflow_id)
            .order_by(WorkflowStep.step_order)
            .all()
        )

        # Create execution record
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            trigger_event_id=trigger_event_id,
            trigger_context=trigger_context,
            status="dry_run" if dry_run else "running",
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        step_results: List[Dict[str, Any]] = []
        overall_success = True

        for step in steps:
            step_result = await _execute_step(step, trigger_context, dry_run)
            step_results.append(step_result)

            if not step_result["success"] and not dry_run:
                overall_success = False
                logger.error(
                    "Step %d of workflow '%s' failed: %s",
                    step.step_order,
                    workflow.name,
                    step_result.get("error"),
                )
                # Log the failure but continue remaining steps
                activity = ActivityLog(
                    workflow_id=workflow_id,
                    action_type="step_failed",
                    description="Step {} ({}) failed: {}".format(
                        step.step_order, step.action_type, step_result.get("error")
                    ),
                )
                db.add(activity)

        # Update execution record
        execution.status = "dry_run" if dry_run else ("completed" if overall_success else "failed")
        execution.results = {"steps": step_results}
        execution.completed_at = datetime.now(timezone.utc)
        if not overall_success:
            execution.error = "One or more steps failed"

        # Activity log for successful execution
        if not dry_run:
            activity = ActivityLog(
                workflow_id=workflow_id,
                action_type="workflow_executed",
                description="Workflow '{}' executed ({})".format(
                    workflow.name, "success" if overall_success else "with errors"
                ),
                details={"trigger_event_id": trigger_event_id, "step_count": len(steps)},
            )
            db.add(activity)

        db.commit()

        return {
            "success": overall_success,
            "execution_id": execution.id,
            "workflow_name": workflow.name,
            "dry_run": dry_run,
            "steps": step_results,
        }

    except Exception as e:
        logger.error("Workflow execution error: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def _execute_step(
    step: WorkflowStep,
    context: Dict[str, Any],
    dry_run: bool,
) -> Dict[str, Any]:
    """Execute or simulate a single workflow step."""
    config = step.action_config or {}

    # Resolve template variables in message/subject fields
    resolved_config = {}
    for key, value in config.items():
        if isinstance(value, str):
            resolved_config[key] = resolve_variables(value, context)
        else:
            resolved_config[key] = value

    # Build params for the action
    params = dict(resolved_config)

    # Map common fields to what integrations expect
    if step.action_type in ("send_sms", "send_template_sms", "send_review_request"):
        params.setdefault("to_phone", context.get("client_phone", ""))
        params.setdefault("message_body", resolved_config.get("message_template", ""))
        if "template_body" not in params:
            params["template_body"] = resolved_config.get("message_template", "")
        params["variables"] = context

    elif step.action_type in ("send_email", "send_template_email"):
        params.setdefault("to_email", context.get("client_email", ""))
        params.setdefault("subject", resolved_config.get("subject", ""))
        params.setdefault("body_html", resolved_config.get("message_template", ""))
        if "subject_template" not in params:
            params["subject_template"] = resolved_config.get("subject", "")
        if "body_template" not in params:
            params["body_template"] = resolved_config.get("message_template", "")
        params["variables"] = context

    result = {
        "step_order": step.step_order,
        "action_type": step.action_type,
        "description": step.description or step.action_type,
        "resolved_params": params,
    }

    if dry_run:
        result["success"] = True
        result["dry_run"] = True
        result["preview"] = _build_preview(step.action_type, params, context)
    else:
        action_result = await route_action(step.action_type, params)
        result["success"] = action_result["success"]
        result["details"] = action_result.get("details")
        result["error"] = action_result.get("error")

    return result


def _build_preview(action_type: str, params: dict, context: dict) -> str:
    """Build a plain-English preview of what this step would do."""
    if action_type in ("send_sms", "send_template_sms", "send_review_request"):
        to = params.get("to_phone") or context.get("client_phone", "[client phone]")
        body = resolve_variables(
            params.get("message_body") or params.get("template_body", ""),
            context,
        )
        return "Send a text to {}: \"{}\"".format(to, body)

    if action_type in ("send_email", "send_template_email"):
        to = params.get("to_email") or context.get("client_email", "[client email]")
        subject = resolve_variables(params.get("subject", params.get("subject_template", "")), context)
        return "Send an email to {} with subject \"{}\"".format(to, subject)

    if action_type == "create_calendar_event":
        return "Create a calendar event: {}".format(params.get("title", ""))

    return "Perform action: {}".format(action_type)
