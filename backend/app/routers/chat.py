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
from app.services.ai_engine import (
    get_ai_response,
    parse_ai_response,
    extract_workflow_from_conversation,
    extract_action_from_conversation,
)
from app.services.workflow_engine import create_workflow_from_draft
from app.services.gmail import send_email
from app.services.calendar import create_event, check_availability, list_upcoming_events

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
    raw_content = await get_ai_response(messages)
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

    if signals["action_request"]:
        # Extract structured action parameters via a second Claude call
        action_type = signals["action_request"]
        params = await extract_action_from_conversation(messages, action_type)
        if params:
            metadata = {
                "message_type": "action_request",
                "action_type": action_type,
                "action_params": params,
            }

    if signals["action_confirmed"]:
        # Find the most recent action request and execute it
        action_meta = _find_latest_action_request(db, conversation.id)
        if action_meta:
            result = await _execute_chat_action(db, action_meta)
            metadata = {
                "message_type": "action_result",
                "action_type": action_meta["action_type"],
                "success": result["status"] == "success",
                "details": result.get("details", {}),
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


async def _execute_chat_action(db: Session, action_meta: dict) -> dict:
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
            result = create_event(
                db,
                summary=params["summary"],
                start_time=params["start_time"],
                end_time=params["end_time"],
                description=params.get("description"),
            )
            description = f"Created calendar event: {params['summary']}"
            details = {
                "summary": params["summary"],
                "start": params["start_time"],
                "end": params["end_time"],
                "event_id": result.get("event_id"),
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
