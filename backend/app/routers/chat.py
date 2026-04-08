from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.conversation import Conversation, Message
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationSummary,
    ConversationDetail,
    MessageResponse,
)
from app.models.activity_log import ActivityLog
from app.models.workflow import Workflow
from app.services.ai_engine import (
    get_ai_response,
    parse_ai_response,
    extract_workflow_from_conversation,
    extract_action_from_conversation,
    match_workflow_by_name,
)
from app.services.workflow_engine import create_workflow_from_draft
from app.services.gmail import send_email
from app.services.calendar import create_event, update_event, check_availability, list_upcoming_events

router = APIRouter(prefix="/api")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Get or create conversation
    if request.conversation_id:
        conversation = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(title="New conversation")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Save the user message
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    db.commit()

    # Build message history for Claude
    history = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.created_at).all()

    messages = [{"role": m.role, "content": m.content} for m in history]

    # Get AI response and parse for signal tags
    tz = request.timezone or "UTC"
    all_workflows = db.query(Workflow).all()
    wf_names = [w.name for w in all_workflows] if all_workflows else None
    raw_content = await get_ai_response(messages, timezone=tz, workflow_names=wf_names)
    signals = parse_ai_response(raw_content)
    clean_content = signals["clean_content"]

    # Build metadata based on signal flags
    metadata = None

    if signals["workflow_ready"]:
        # Run the hidden extraction call to get structured workflow data
        draft = await extract_workflow_from_conversation(messages)
        if draft:
            metadata = {"message_type": "workflow_summary", "workflow_draft": draft}

    if signals["workflow_confirmed"]:
        # Find the most recent workflow draft in this conversation
        draft = _find_latest_draft(db, conversation.id)
        if draft:
            workflow = create_workflow_from_draft(db, draft, conversation.id)
            metadata = {"message_type": "workflow_confirmed", "workflow_id": workflow.id}

    # Detect action request — from tag or from response content as fallback
    action_request_type = signals["action_request"] or _detect_action_from_content(clean_content)

    if action_request_type:
        # Extract structured action parameters via a second Claude call
        params = await extract_action_from_conversation(messages, action_request_type, timezone=tz)
        metadata = {
            "message_type": "action_request",
            "action_type": action_request_type,
            "action_params": params or {},
        }

    if signals["action_confirmed"]:
        # Determine action type: from the confirmed tag, from a prior action_request, or None
        confirmed_val = signals["action_confirmed"]
        action_meta = _find_latest_action_request(db, conversation.id)

        if isinstance(confirmed_val, str):
            # Claude included the action type in <action_confirmed>send_email</action_confirmed>
            action_type = confirmed_val
        elif action_meta:
            action_type = action_meta["action_type"]
        else:
            action_type = None

        if action_type:
            # Re-extract params from the full conversation (captures any additions)
            fresh_params = await extract_action_from_conversation(
                messages, action_type, timezone=tz
            )
            exec_meta = {
                "action_type": action_type,
                "action_params": fresh_params or (action_meta or {}).get("action_params", {}),
            }
            result = await _execute_chat_action(db, exec_meta, conversation_id=conversation.id)
            metadata = {
                "message_type": "action_result",
                "action_type": action_type,
                "success": result["status"] == "success",
                "details": result.get("details", {}),
            }

    # ── Workflow management (pause / resume / delete) ──────────────────
    if signals["workflow_manage"]:
        manage = signals["workflow_manage"]
        matched = match_workflow_by_name(all_workflows, manage["workflow_name"])
        if matched:
            metadata = {
                "message_type": "workflow_manage_request",
                "manage_action": manage["action"],
                "workflow_id": matched.id,
                "workflow_name": matched.name,
                "workflow_status": matched.status,
            }
        else:
            metadata = {
                "message_type": "workflow_manage_not_found",
                "manage_action": manage["action"],
                "query": manage["workflow_name"],
            }

    if signals["workflow_manage_confirmed"]:
        manage = signals["workflow_manage_confirmed"]
        # Find the pending management request from a prior message
        prior = _find_latest_manage_request(db, conversation.id)
        wf_id = prior.get("workflow_id") if prior else None

        if not wf_id:
            # Fallback: try matching by name again
            matched = match_workflow_by_name(all_workflows, manage["workflow_name"])
            wf_id = matched.id if matched else None

        if wf_id:
            result = _execute_workflow_manage(db, manage["action"], wf_id)
            metadata = {
                "message_type": "workflow_manage_result",
                "manage_action": manage["action"],
                "success": result["success"],
                "workflow_name": result.get("workflow_name", manage["workflow_name"]),
                "detail": result.get("detail", ""),
            }
        else:
            metadata = {
                "message_type": "workflow_manage_result",
                "manage_action": manage["action"],
                "success": False,
                "workflow_name": manage["workflow_name"],
                "detail": "Could not find that workflow.",
            }

    # Save assistant message
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=clean_content,
        metadata_json=metadata,
    )
    db.add(assistant_message)

    # Auto-title from first user message
    if conversation.title == "New conversation":
        conversation.title = request.message[:80]

    db.commit()
    db.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation.id,
        message=MessageResponse.model_validate(assistant_message),
    )


import re as _re


def _detect_action_from_content(content: str) -> Optional[str]:
    """Fallback: detect if the AI response is asking for confirmation of an action.

    Returns the action type if detected, None otherwise.
    """
    lower = content.lower()

    # Must end with a confirmation question
    confirmation_phrases = [
        "sound good", "want me to", "shall i", "go ahead",
        "ready to", "look right", "look correct", "that right",
        "does that work", "want me to go", "should i",
    ]
    has_confirmation = any(phrase in lower for phrase in confirmation_phrases)
    if not has_confirmation:
        return None

    # Detect action type from keywords
    if _re.search(r"\bemail\b|\bsend\b.*\bto\b.*@", lower):
        return "send_email"
    if _re.search(r"\bevent\b|\bcalendar\b|\bmeeting\b|\bappointment\b", lower):
        return "create_event"
    if _re.search(r"\bavailab|\bfree\b|\bbusy\b|\bopen\b.*\bslot", lower):
        return "check_availability"
    if _re.search(r"\badd\b.*\b(attend|invite)\b|\binvite\b.*\bto\b", lower):
        return "update_event"

    return None


def _find_latest_draft(db: Session, conversation_id: int) -> Optional[dict]:
    """Walk backward through conversation messages to find the most recent workflow draft."""
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.role == "assistant",
    ).order_by(Message.created_at.desc()).all()

    for msg in messages:
        if msg.metadata_json and isinstance(msg.metadata_json, dict):
            if msg.metadata_json.get("message_type") == "workflow_summary":
                return msg.metadata_json.get("workflow_draft")
    return None


def _find_latest_action_request(db: Session, conversation_id: int) -> Optional[dict]:
    """Walk backward through conversation messages to find the most recent action request."""
    msgs = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.role == "assistant",
    ).order_by(Message.created_at.desc()).all()

    for msg in msgs:
        if msg.metadata_json and isinstance(msg.metadata_json, dict):
            if msg.metadata_json.get("message_type") == "action_request":
                return msg.metadata_json
    return None


def _find_latest_event_id(db: Session, conversation_id: int) -> Optional[str]:
    """Find the most recent event_id from an action_result in this conversation."""
    msgs = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.role == "assistant",
    ).order_by(Message.created_at.desc()).all()

    for msg in msgs:
        if msg.metadata_json and isinstance(msg.metadata_json, dict):
            if msg.metadata_json.get("message_type") == "action_result":
                details = msg.metadata_json.get("details", {})
                event_id = details.get("event_id")
                if event_id:
                    return event_id
    return None


async def _execute_chat_action(db: Session, action_meta: dict, conversation_id: Optional[int] = None) -> dict:
    """Execute an action from chat and log it to the activity log."""
    action_type = action_meta["action_type"]
    params = action_meta.get("action_params", {})

    try:
        if action_type == "send_email":
            result = send_email(db, params["recipient"], params["subject"], params["body"])
            description = f"Sent email to {params['recipient']}: {params['subject']}"
            details = {
                "recipient": params["recipient"],
                "subject": params["subject"],
                "gmail_message_id": result.get("message_id"),
                "source": "chat",
            }

        elif action_type == "create_event":
            attendees = params.get("attendees")
            result = create_event(
                db,
                summary=params["summary"],
                start_time=params["start_time"],
                end_time=params["end_time"],
                description=params.get("description"),
                attendees=attendees,
            )
            description = f"Created calendar event: {params['summary']}"
            if attendees:
                description += f" (invited: {', '.join(attendees)})"
            details = {
                "summary": params["summary"],
                "start": params["start_time"],
                "end": params["end_time"],
                "event_id": result.get("event_id"),
                "attendees": attendees,
                "source": "chat",
            }

        elif action_type == "update_event":
            event_id = _find_latest_event_id(db, conversation_id) if conversation_id else None
            if not event_id:
                return {"status": "error", "details": {"error": "No recent event found to update"}}
            result = update_event(
                db,
                event_id=event_id,
                add_attendees=params.get("add_attendees"),
                summary=params.get("summary"),
            )
            add_list = params.get("add_attendees", [])
            description = f"Updated calendar event: {result.get('summary')}"
            if add_list:
                description += f" (added: {', '.join(add_list)})"
            details = {
                "event_id": event_id,
                "summary": result.get("summary"),
                "attendees_added": add_list,
                "source": "chat",
            }

        elif action_type == "check_availability":
            result = check_availability(db, params["start_time"], params["end_time"])
            description = f"Checked availability: {params['start_time']} to {params['end_time']}"
            details = {"result": result, "source": "chat"}

        elif action_type == "list_events":
            events = list_upcoming_events(db, max_results=5)
            description = "Listed upcoming calendar events"
            details = {"events": events, "count": len(events), "source": "chat"}
            result = {"events": events, "count": len(events)}

        else:
            return {"status": "error", "details": {"error": f"Unknown action type: {action_type}"}}

        # Log to activity
        log = ActivityLog(
            action_type=action_type,
            description=description,
            details=details,
        )
        db.add(log)
        db.commit()

        return {"status": "success", "details": result}

    except Exception as e:
        return {"status": "error", "details": {"error": str(e)}}


def _find_latest_manage_request(db: Session, conversation_id: int) -> Optional[dict]:
    """Find the most recent workflow_manage_request metadata in this conversation."""
    msgs = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.role == "assistant",
    ).order_by(Message.created_at.desc()).all()

    for msg in msgs:
        if msg.metadata_json and isinstance(msg.metadata_json, dict):
            if msg.metadata_json.get("message_type") == "workflow_manage_request":
                return msg.metadata_json
    return None


def _execute_workflow_manage(db: Session, action: str, workflow_id: int) -> dict:
    """Execute a workflow management action (pause/resume/delete)."""
    from datetime import datetime, timezone
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        return {"success": False, "detail": "Workflow not found"}

    workflow_name = workflow.name

    if action == "delete":
        from app.models.workflow import WorkflowStep
        db.query(WorkflowStep).filter(WorkflowStep.workflow_id == workflow_id).delete()
        log = ActivityLog(
            action_type="workflow_deleted",
            description=f"Workflow '{workflow_name}' was deleted via chat",
            details={"workflow_id": workflow_id, "workflow_name": workflow_name, "source": "chat"},
        )
        db.add(log)
        db.delete(workflow)
        db.commit()
        return {"success": True, "workflow_name": workflow_name, "detail": f"'{workflow_name}' has been deleted."}

    # Pause or resume
    new_status = "paused" if action == "pause" else "active"
    allowed = {"draft": ["active", "paused"], "testing": ["active", "paused"], "active": ["paused"], "paused": ["active"]}
    if new_status not in allowed.get(workflow.status, []):
        return {
            "success": False,
            "workflow_name": workflow_name,
            "detail": f"Can't {action} — it's currently '{workflow.status}'.",
        }

    old_status = workflow.status
    workflow.status = new_status
    workflow.updated_at = datetime.now(timezone.utc)

    log = ActivityLog(
        workflow_id=workflow.id,
        action_type="workflow_status_change",
        description=f"Workflow '{workflow_name}' changed from {old_status} to {new_status} via chat",
        details={"old_status": old_status, "new_status": new_status, "source": "chat"},
    )
    db.add(log)
    db.commit()

    verb = "paused" if action == "pause" else "resumed"
    return {"success": True, "workflow_name": workflow_name, "detail": f"'{workflow_name}' has been {verb}."}


@router.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations(db: Session = Depends(get_db)):
    conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [ConversationSummary.model_validate(c) for c in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetail.model_validate(conversation)
