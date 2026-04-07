import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.conversation import Conversation, Message
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationSummary,
    ConversationDetail,
)
from app.services.ai_engine import get_ai_response, generate_title
from app.services.workflow_extractor import extract_workflow

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_HISTORY = 50
WORKFLOW_ACK_INSTRUCTION = (
    "IMPORTANT: The task the owner just confirmed has been saved successfully. "
    "In your response, let them know it's been saved and is currently in test mode. "
    "Ask if they'd like to set up another task or see what this one will look like in action."
)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    is_new = request.conversation_id is None
    workflow_saved = False

    # Get or create conversation
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(title="New Conversation")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Store user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # Build message history for Claude (capped at MAX_HISTORY)
    all_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .all()
    )

    recent = all_messages[-MAX_HISTORY:] if len(all_messages) > MAX_HISTORY else all_messages
    history = [{"role": m.role, "content": m.content} for m in recent]

    # Check if we need to inject workflow acknowledgment
    extra_system = None
    if conversation.workflow_id:
        already_acked = any(
            m.metadata_ and m.metadata_.get("workflow_acknowledged")
            for m in all_messages
            if m.role == "assistant"
        )
        if not already_acked:
            extra_system = WORKFLOW_ACK_INSTRUCTION
            workflow_saved = True

    # Get AI response
    ai_text = await get_ai_response(history, extra_system=extra_system)

    # Store assistant response
    metadata = None
    if workflow_saved:
        metadata = {"workflow_acknowledged": True}

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=ai_text,
        metadata_=metadata,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    # Background: generate title for new conversations
    if is_new:
        background_tasks.add_task(_generate_title_bg, conversation.id, request.message)

    # Background: check for workflow extraction
    background_tasks.add_task(_extract_workflow_bg, conversation.id)

    return ChatResponse(
        response=ai_text,
        conversation_id=conversation.id,
        message_id=assistant_msg.id,
        workflow_saved=workflow_saved,
    )


@router.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations(db: Session = Depends(get_db)):
    conversations = (
        db.query(Conversation)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return conversations


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


# --- Background task helpers ---

async def _generate_title_bg(conversation_id: str, first_message: str):
    """Generate an AI-powered title for a new conversation."""
    try:
        title = await generate_title(first_message)
        db = SessionLocal()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conv:
                conv.title = title
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error("Title generation failed: %s", e)


async def _extract_workflow_bg(conversation_id: str):
    """Run workflow extraction in the background."""
    try:
        await extract_workflow(conversation_id)
    except Exception as e:
        logger.error("Workflow extraction failed: %s", e)
