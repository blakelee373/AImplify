"""Backend state machine for immediate-action field collection.

Replaces the AI-driven signal tag system (<action_request>, <action_confirmed>)
with deterministic field tracking. The backend controls what card appears and when.
"""

from typing import Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session

from app.models.action_form import ActionFormState


# ---------------------------------------------------------------------------
# Field schemas — source of truth for what each action type requires
# ---------------------------------------------------------------------------

REQUIRED_FIELD_SCHEMAS: Dict[str, dict] = {
    "send_email": {
        "required": ["recipient", "subject", "body"],
        "optional": ["cc", "bcc"],
        "auto_execute": False,
    },
    "create_event": {
        "required": ["summary", "start_time", "end_time"],
        "optional": ["description", "attendees"],
        "auto_execute": False,
    },
    "update_event": {
        "required": [],  # At least one optional field must be set
        "optional": ["add_attendees", "summary"],
        "auto_execute": False,
    },
    "list_events": {
        "required": [],
        "optional": ["time_min", "time_max"],
        "auto_execute": True,
    },
    "check_availability": {
        "required": ["start_time", "end_time"],
        "optional": [],
        "auto_execute": False,
        "skip_confirmation": True,  # Execute immediately once fields are filled
    },
}

# Trigger field schemas (for documentation and future workflow state machine)
TRIGGER_FIELD_SCHEMAS: Dict[str, dict] = {
    "calendar_event_created": {
        "required": ["description"],
        "optional": [
            "summary_contains",
            "attendee_email",
            "description_contains",
            "min_duration_minutes",
        ],
    },
    "calendar_event_starting": {
        "required": ["lead_time_minutes", "description"],
        "optional": [
            "summary_contains",
            "attendee_email",
            "description_contains",
            "min_duration_minutes",
        ],
    },
    "email_received": {
        "required": ["gmail_query_description"],
        "optional": [],
    },
    "schedule": {
        "required": ["frequency", "schedule_time"],
        "optional": [],
    },
}

# Human-readable prompts for each field — tells the AI what to ask about
FIELD_PROMPTS: Dict[str, str] = {
    "recipient": "who to send the email to (their email address)",
    "subject": "the email subject line",
    "body": "what the email should say",
    "cc": "who to CC on the email",
    "bcc": "who to BCC on the email",
    "summary": "the event title/name",
    "start_time": "when it should start (date and time)",
    "end_time": "when it should end, or how long it should be",
    "description": "any notes or description to include",
    "attendees": "who to invite (their email addresses)",
    "add_attendees": "who to add to the event (their email addresses)",
}

ACTION_LABELS: Dict[str, str] = {
    "send_email": "send an email",
    "create_event": "create a calendar event",
    "update_event": "update a calendar event",
    "check_availability": "check calendar availability",
    "list_events": "list calendar events",
}


# ---------------------------------------------------------------------------
# Form state CRUD
# ---------------------------------------------------------------------------


def get_active_form(db: Session, conversation_id: int) -> Optional[ActionFormState]:
    """Return the active form state for a conversation (collecting or ready)."""
    return (
        db.query(ActionFormState)
        .filter(
            ActionFormState.conversation_id == conversation_id,
            ActionFormState.status.in_(["collecting", "ready"]),
        )
        .first()
    )


def create_form_state(
    db: Session, conversation_id: int, action_type: str
) -> ActionFormState:
    """Create a new form state, cancelling any existing active form first."""
    existing = get_active_form(db, conversation_id)
    if existing:
        existing.status = "cancelled"
        db.flush()

    schema = REQUIRED_FIELD_SCHEMAS.get(action_type, {"required": [], "optional": []})
    fields = {f: None for f in schema["required"]}

    form = ActionFormState(
        conversation_id=conversation_id,
        action_type=action_type,
        fields=fields,
        status="collecting",
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    return form


def update_form_fields(
    db: Session, form_state: ActionFormState, extracted: Dict[str, Any]
) -> None:
    """Merge extracted field values into the form state (non-null values only)."""
    current = dict(form_state.fields) if form_state.fields else {}
    changed = False
    for key in current:
        val = extracted.get(key)
        if val is not None:
            current[key] = val
            changed = True
    # Also pick up optional fields if they were provided
    schema = REQUIRED_FIELD_SCHEMAS.get(
        form_state.action_type, {"required": [], "optional": []}
    )
    for key in schema.get("optional", []):
        val = extracted.get(key)
        if val is not None:
            current[key] = val
            changed = True
    if changed:
        form_state.fields = current
        db.commit()
        db.refresh(form_state)


def check_completion(form_state: ActionFormState) -> bool:
    """Return True if all required fields are non-null."""
    schema = REQUIRED_FIELD_SCHEMAS.get(
        form_state.action_type, {"required": [], "optional": []}
    )
    required = schema["required"]
    if not required:
        # update_event: at least one optional field must be set
        if form_state.action_type == "update_event":
            return any(v is not None for v in (form_state.fields or {}).values())
        return True
    fields = form_state.fields or {}
    return all(fields.get(f) is not None for f in required)


def get_next_missing_field(form_state: ActionFormState) -> Optional[Tuple[str, str]]:
    """Return (field_name, prompt_hint) for the next missing required field."""
    schema = REQUIRED_FIELD_SCHEMAS.get(
        form_state.action_type, {"required": [], "optional": []}
    )
    fields = form_state.fields or {}
    for f in schema["required"]:
        if fields.get(f) is None:
            return (f, FIELD_PROMPTS.get(f, f))
    return None


def build_form_context(form_state: ActionFormState) -> str:
    """Build a system prompt addendum describing the active field collection."""
    fields = form_state.fields or {}
    filled = {k: v for k, v in fields.items() if v is not None}
    missing = get_next_missing_field(form_state)

    label = ACTION_LABELS.get(form_state.action_type, form_state.action_type)

    if missing is None:
        # No required fields missing — but for all-optional actions (update_event),
        # prompt for the first optional field if nothing has been collected yet
        if not filled:
            schema = REQUIRED_FIELD_SCHEMAS.get(form_state.action_type, {})
            optional = schema.get("optional", [])
            if optional:
                first_opt = optional[0]
                hint = FIELD_PROMPTS.get(first_opt, first_opt)
                return (
                    f"\n\nACTIVE ACTION: The user is working on: {label}.\n"
                    f"NEXT FIELD NEEDED: {first_opt} — {hint}.\n"
                    "Ask ONE natural question about this field. "
                    "Offer 2-3 choices when possible."
                )
        # All fields collected — tell AI to write a brief confirmation
        return (
            f"\n\nACTIVE ACTION: The user is working on: {label}.\n"
            f"Collected so far: {filled}\n"
            "All required fields are collected. Write a brief confirmation summary "
            "like 'Here\\'s what I\\'ll do:' — the system will show a details card automatically."
        )

    field_name, prompt_hint = missing
    parts = [f"\n\nACTIVE ACTION: The user is working on: {label}."]
    if filled:
        parts.append(f"Already collected: {filled}")
    parts.append(
        f"NEXT FIELD NEEDED: {field_name} — {prompt_hint}.\n"
        "Ask ONE natural question about this field. Offer 2-3 choices when possible. "
        "Do NOT summarize or confirm yet — the system handles that automatically."
    )
    return "\n".join(parts)


def is_auto_execute(action_type: str) -> bool:
    """Return True if this action type should execute immediately without confirmation."""
    schema = REQUIRED_FIELD_SCHEMAS.get(action_type, {})
    return schema.get("auto_execute", False)


def is_skip_confirmation(action_type: str) -> bool:
    """Return True if this action type should execute once fields are filled (no confirmation card)."""
    schema = REQUIRED_FIELD_SCHEMAS.get(action_type, {})
    return schema.get("skip_confirmation", False)
