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
from app.services.ai_engine import (
    get_ai_response,
    parse_ai_response,
    extract_workflow_from_conversation,
)
from app.services.workflow_engine import create_workflow_from_draft

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
    clean_content, workflow_ready, workflow_confirmed = parse_ai_response(raw_content)

    # Build metadata based on signal flags
    metadata = None

    if workflow_ready:
        # Run the hidden extraction call to get structured workflow data
        draft = await extract_workflow_from_conversation(messages)
        if draft:
            metadata = {"message_type": "workflow_summary", "workflow_draft": draft}

    if workflow_confirmed:
        # Find the most recent workflow draft in this conversation
        draft = _find_latest_draft(db, conversation.id)
        if draft:
            workflow = create_workflow_from_draft(db, draft, conversation.id)
            metadata = {"message_type": "workflow_confirmed", "workflow_id": workflow.id}

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
