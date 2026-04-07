"""Background service that analyzes conversations for confirmed workflows."""

import json
import logging
from typing import Optional

from app.database import SessionLocal
from app.models.conversation import Conversation, Message
from app.models.workflow import Workflow, WorkflowStep
from app.models.activity_log import ActivityLog
from app.services.ai_engine import client

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Analyze the following conversation between a business owner and an AI assistant. Determine if a complete, confirmed workflow has been described.

A workflow is "complete" when ALL of these are known:
- Trigger: what event starts this task
- Action: what should happen
- Target: who is affected
- Timing: when it should happen
- Content: what the message/action contains (at least a rough version)

A workflow is "confirmed" when the owner has explicitly agreed to the summary (said "yes," "looks good," "that's right," "perfect," "confirmed," or similar).

If a complete and confirmed workflow exists, respond with ONLY a JSON object in this exact format:
{
  "workflow_detected": true,
  "workflow": {
    "name": "Short descriptive name",
    "description": "One sentence plain English description",
    "trigger_type": "event_based | time_based | condition_based",
    "trigger_description": "Plain English trigger",
    "trigger_config": {
      "event": "new_booking | appointment_completed | appointment_cancelled | no_show | new_lead | time_schedule | days_since_last_visit | missed_call",
      "delay_minutes": 0,
      "schedule": null
    },
    "steps": [
      {
        "step_order": 1,
        "action_type": "send_sms | send_email | create_task | update_record | send_review_request | create_reminder",
        "description": "Plain English description of this step",
        "config": {
          "recipient_type": "client | staff | owner",
          "message_template": "The actual message text with {{client_name}} and other placeholders",
          "subject": "Email subject if applicable"
        }
      }
    ],
    "conditions": [
      "Any conditions or exceptions mentioned, as plain English strings"
    ]
  }
}

If no complete and confirmed workflow exists yet, respond with ONLY:
{
  "workflow_detected": false,
  "reason": "Brief explanation of what's still missing"
}

Do NOT include any text outside the JSON object. Only return valid JSON."""


async def extract_workflow(conversation_id: str) -> Optional[dict]:
    """Analyze a conversation and extract a confirmed workflow if present."""
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conversation:
            return None

        # Skip if workflow already saved for this conversation
        if conversation.workflow_id:
            return None

        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()

        # Need enough back-and-forth for a complete workflow
        if len(messages) < 4:
            return None

        # Build conversation transcript for analysis
        transcript = "\n".join(
            "{}: {}".format("Owner" if m.role == "user" else "Assistant", m.content)
            for m in messages
        )

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=EXTRACTION_PROMPT,
            messages=[{"role": "user", "content": transcript}],
        )

        result_text = response.content[0].text.strip()

        # Handle markdown code fences Claude sometimes adds
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        result = json.loads(result_text)

        if not result.get("workflow_detected"):
            return None

        workflow_data = result["workflow"]

        # Save the workflow
        workflow = Workflow(
            name=workflow_data["name"],
            description=workflow_data.get("description"),
            status="draft",
            trigger_type=workflow_data.get("trigger_type"),
            trigger_description=workflow_data.get("trigger_description"),
            trigger_config=workflow_data.get("trigger_config"),
            conditions=workflow_data.get("conditions"),
        )
        db.add(workflow)
        db.commit()
        db.refresh(workflow)

        for step_data in workflow_data.get("steps", []):
            step = WorkflowStep(
                workflow_id=workflow.id,
                step_order=step_data["step_order"],
                action_type=step_data["action_type"],
                description=step_data.get("description"),
                action_config=step_data.get("config"),
            )
            db.add(step)

        # Link conversation to workflow
        conversation.workflow_id = workflow.id

        # Log the creation
        activity = ActivityLog(
            workflow_id=workflow.id,
            action_type="workflow_created",
            description="Workflow '{}' created from conversation".format(workflow.name),
        )
        db.add(activity)

        db.commit()
        logger.info("Workflow '%s' extracted and saved from conversation %s", workflow.name, conversation_id)
        return result

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse extraction result: %s", e)
        return None
    except Exception as e:
        logger.error("Workflow extraction error: %s", e)
        return None
    finally:
        db.close()
