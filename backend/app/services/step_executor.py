"""Step executor — maps workflow steps to real actions with AI-generated parameters."""

from typing import Dict, Optional
from anthropic import AsyncAnthropic
from sqlalchemy.orm import Session

from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from app.services.gmail import send_email
from app.services.calendar import create_event, check_availability

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# ── Parameter generation tools ───────────────────────────────────────────────

EMAIL_PARAMS_TOOL = {
    "name": "email_params",
    "description": "Generate email parameters for sending.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Email address of the recipient",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line",
            },
            "body": {
                "type": "string",
                "description": "Full email body text, friendly and professional",
            },
        },
        "required": ["recipient", "subject", "body"],
    },
}

EVENT_PARAMS_TOOL = {
    "name": "event_params",
    "description": "Generate calendar event parameters.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Event title",
            },
            "start_time": {
                "type": "string",
                "description": "ISO 8601 start time (e.g., '2026-04-10T14:00:00Z')",
            },
            "end_time": {
                "type": "string",
                "description": "ISO 8601 end time (e.g., '2026-04-10T15:00:00Z')",
            },
            "description": {
                "type": "string",
                "description": "Event description / notes",
            },
        },
        "required": ["summary", "start_time", "end_time"],
    },
}

AVAILABILITY_PARAMS_TOOL = {
    "name": "availability_params",
    "description": "Generate time range for checking calendar availability.",
    "input_schema": {
        "type": "object",
        "properties": {
            "start_time": {
                "type": "string",
                "description": "ISO 8601 start time",
            },
            "end_time": {
                "type": "string",
                "description": "ISO 8601 end time",
            },
        },
        "required": ["start_time", "end_time"],
    },
}

PARAM_GEN_SYSTEM = """\
You are a parameter generator for an AI automation system. Given a workflow step \
description and runtime context, generate the exact parameters needed to execute \
the action. Be specific, professional, and use information from the context to \
personalize the output. Use the provided tool to return the parameters.

You ARE connected to the owner's Gmail and Google Calendar. You CAN send emails \
and create events. NEVER claim you can't do something — just generate the parameters.

IMPORTANT — When the step says "yourself", "self", "me", or "the owner", use the \
owner_email or client_email from the runtime context as the recipient. \
NEVER use placeholder emails like "me@example.com" or "self" — always use the \
actual email address from the context.

SAVED STEP CONFIG — When a "Saved step config" section is provided, use those values \
as the basis for your parameters. If a "message" or "body" field is provided, use that \
as the email body. If a "subject" field is provided, use that as the subject line. \
Do NOT ignore saved config — the owner specifically set these values.

EMAIL-TRIGGERED WORKFLOWS — When the context contains email_sender, email_subject, \
and email_snippet, this workflow was triggered by an incoming email. \
For reply/response steps, use email_sender as the recipient. \
You can reference the original email's subject and content to personalize the response. \
Example: if email_sender is "jane@example.com" and the step says "send welcome reply", \
set recipient to "jane@example.com".

CALENDAR-TRIGGERED WORKFLOWS — When the context contains calendar_event_summary, \
calendar_event_start, and calendar_event_end, this workflow was triggered by a calendar event. \
For notification/email steps, reference the event details to personalize the message. \
calendar_event_attendees contains a comma-separated list of attendee emails. \
Example: if calendar_event_summary is "Consultation with Jane" and calendar_event_start \
is "2026-04-10T14:00:00-05:00", include the event title and formatted time in the email body.

For dates and times, use the day reference below to convert day names to exact dates. \
Always produce full ISO 8601 timestamps with the correct timezone offset.\
"""

# ── Map action_type to (tool, service function) ─────────────────────────────

ACTION_MAP = {
    "send_email": {
        "tool": EMAIL_PARAMS_TOOL,
        "aliases": ["send_email", "email", "send_welcome_email", "send_reminder"],
    },
    "create_event": {
        "tool": EVENT_PARAMS_TOOL,
        "aliases": ["create_event", "create_calendar_event", "schedule_event", "add_calendar_event", "schedule"],
    },
    "check_calendar": {
        "tool": AVAILABILITY_PARAMS_TOOL,
        "aliases": ["check_calendar", "check_availability", "check_schedule"],
    },
}


def _resolve_action_type(raw_type: str) -> Optional[str]:
    """Normalize action_type aliases to a canonical key."""
    raw = raw_type.lower().strip()
    for canonical, info in ACTION_MAP.items():
        if raw in info["aliases"] or raw == canonical:
            return canonical
    return None


async def _generate_params(
    tool: dict,
    step_description: str,
    workflow_name: str,
    context: Dict,
) -> Optional[dict]:
    """Use Claude to generate action parameters from the step description and context."""
    from datetime import datetime, timedelta, timezone as tz
    from zoneinfo import ZoneInfo

    context_str = "\n".join(f"- {k}: {v}" for k, v in context.items()) if context else "No additional context provided."

    # Build timezone-aware date reference
    user_tz = context.get("timezone", "UTC")
    try:
        now = datetime.now(ZoneInfo(user_tz))
    except Exception:
        now = datetime.now(tz.utc)

    day_lines = []
    for i in range(7):
        d = now + timedelta(days=i)
        label = "Today" if i == 0 else "Tomorrow" if i == 1 else d.strftime("%A")
        day_lines.append(f"- {label}: {d.strftime('%A, %B %d, %Y')}")
    week_ref = "\n".join(day_lines)

    system = PARAM_GEN_SYSTEM + f"\n\nToday is {now.strftime('%A, %B %d, %Y')}. Timezone: {user_tz}.\n\nUpcoming days:\n{week_ref}"

    # Include action_config in the prompt so AI uses saved values
    config_str = ""
    if context.get("_action_config"):
        cfg = context["_action_config"]
        config_str = "\nSaved step config (use these values when present):\n"
        config_str += "\n".join(f"- {k}: {v}" for k, v in cfg.items())

    user_message = (
        f"Workflow: {workflow_name}\n"
        f"Step: {step_description}\n"
        f"{config_str}\n"
        f"Runtime context:\n{context_str}\n\n"
        f"Generate the parameters for this action."
    )

    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == tool["name"]:
                return block.input

        return None
    except Exception:
        return None


async def execute_step(
    db: Session,
    action_type: str,
    step_description: str,
    workflow_name: str,
    action_config: Optional[dict],
    context: Dict,
) -> dict:
    """Execute a single workflow step.

    1. Resolve the action type
    2. Generate parameters via AI (merging any existing action_config)
    3. Call the appropriate service

    Returns {"status": "success"|"error", "action": str, "details": dict}
    """
    canonical = _resolve_action_type(action_type)
    if not canonical:
        # Skip unrecognized steps (e.g., filter/check steps in email-triggered
        # workflows) instead of failing — the gmail_query handles filtering.
        return {
            "status": "success",
            "action": action_type,
            "details": {"skipped": True, "reason": f"No executor for action type: {action_type}"},
        }

    action_info = ACTION_MAP[canonical]
    tool = action_info["tool"]

    # Pass action_config into context so AI can see saved values
    gen_context = dict(context)
    if action_config:
        gen_context["_action_config"] = action_config

    # Generate params from AI
    params = await _generate_params(tool, step_description, workflow_name, gen_context)

    if not params:
        return {
            "status": "error",
            "action": canonical,
            "details": {"error": "Failed to generate parameters for this step"},
        }

    # Merge action_config, but skip time values that aren't full ISO 8601
    # timestamps — the AI generates proper timestamps and bare times like
    # "2:00 PM" or "14:00" from action_config would overwrite them.
    if action_config:
        import re as _merge_re
        iso_pattern = _merge_re.compile(r"^\d{4}-\d{2}-\d{2}T")
        skip_keys = {"duration_minutes", "duration", "title"}
        for key, value in action_config.items():
            if key in skip_keys:
                continue  # Internal metadata, not an API parameter
            if key in ("start_time", "end_time") and isinstance(value, str) and not iso_pattern.match(value):
                continue  # Skip non-ISO times — AI generated proper timestamps
            params[key] = value

    try:
        if canonical == "send_email":
            result = send_email(db, params["recipient"], params["subject"], params["body"])
            return {"status": "success", "action": "send_email", "details": result}

        elif canonical == "create_event":
            result = create_event(
                db,
                summary=params["summary"],
                start_time=params["start_time"],
                end_time=params["end_time"],
                description=params.get("description"),
            )
            return {"status": "success", "action": "create_event", "details": result}

        elif canonical == "check_calendar":
            result = check_availability(db, params["start_time"], params["end_time"])
            return {"status": "success", "action": "check_calendar", "details": result}

    except ValueError as e:
        return {"status": "error", "action": canonical, "details": {"error": str(e)}}
    except Exception as e:
        return {"status": "error", "action": canonical, "details": {"error": str(e)}}

    return {"status": "error", "action": canonical, "details": {"error": "Unhandled action"}}
