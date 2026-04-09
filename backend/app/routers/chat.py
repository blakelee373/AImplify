from datetime import datetime, timezone
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
from app.models.integration import Integration
from app.models.workflow import Workflow
from app.services.ai_engine import (
    get_ai_response,
    parse_ai_response,
    extract_workflow_from_conversation,
    extract_action_from_conversation,
    extract_run_context_from_conversation,
    extract_schedule_from_conversation,
    match_workflow_by_name,
)
from app.services.workflow_engine import create_workflow_from_draft
from app.services.workflow_runner import run_workflow
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

    messages = []
    for m in history:
        content = m.content
        # Inject action results into assistant messages so Claude sees outcomes
        if m.role == "assistant" and m.metadata_json and isinstance(m.metadata_json, dict):
            msg_type = m.metadata_json.get("message_type")
            if msg_type == "action_result":
                action_type = m.metadata_json.get("action_type", "")
                details = m.metadata_json.get("details", {})
                success = m.metadata_json.get("success", False)
                if action_type == "list_events" and success:
                    events = details.get("events", [])
                    if events:
                        lines = []
                        for ev in events:
                            lines.append(f"- {ev.get('summary', '(No title)')} | {ev.get('start', '')} to {ev.get('end', '')}")
                        content += "\n\n[System: Calendar returned these events:\n" + "\n".join(lines) + "]"
                    else:
                        content += "\n\n[System: Calendar returned no events for that time range.]"
                elif action_type == "check_availability" and success:
                    avail = details.get("available", None)
                    conflicts = details.get("conflicts", [])
                    if avail is None:
                        # Fallback: nested under "result" key
                        nested = details.get("result", {})
                        avail = nested.get("available", None)
                        conflicts = nested.get("conflicts", [])
                    if avail:
                        content += "\n\n[System: That time slot is available — no conflicts.]"
                    else:
                        conflict_lines = [f"- {c.get('start', '')} to {c.get('end', '')}" for c in conflicts]
                        content += "\n\n[System: That time slot is NOT available. Conflicts:\n" + "\n".join(conflict_lines) + "]"
                elif success:
                    content += f"\n\n[System: Action '{action_type}' completed successfully. Details: {details}]"
                else:
                    error = details.get("error", "Unknown error")
                    content += f"\n\n[System: Action '{action_type}' failed. Error: {error}]"
            elif msg_type == "action_request":
                # Let Claude know a confirmation card was shown so it emits
                # <action_confirmed> (not another <action_request>) when the user says "yes"
                action_type = m.metadata_json.get("action_type", "")
                content += f"\n\n[System: A confirmation card for '{action_type}' is being shown to the user. " \
                           "When they confirm, respond with a short acknowledgment and use <action_confirmed> — " \
                           "do NOT re-summarize or show another <action_request>.]"
            elif msg_type == "connect_tool":
                provider = m.metadata_json.get("provider", "")
                content += f"\n\n[System: A 'Connect' button for '{provider}' is being shown to the user. " \
                           "Wait for them to complete the connection.]"
            elif msg_type == "disconnect_request":
                provider = m.metadata_json.get("provider", "")
                content += f"\n\n[System: A disconnect confirmation for '{provider}' is being shown. " \
                           "When they confirm, respond with a short acknowledgment and use <disconnect_confirmed> — " \
                           "do NOT re-summarize or show another <disconnect_tool>.]"
            elif msg_type == "disconnect_result":
                provider = m.metadata_json.get("provider", "")
                success = m.metadata_json.get("success", False)
                if success:
                    content += f"\n\n[System: {provider} has been disconnected successfully.]"
                else:
                    content += f"\n\n[System: Failed to disconnect {provider}.]"
            elif msg_type == "workflow_manage_request":
                action = m.metadata_json.get("manage_action", "")
                wf_name = m.metadata_json.get("workflow_name", "")
                content += f"\n\n[System: A confirmation card to {action} '{wf_name}' is being shown. " \
                           "When they confirm, respond with a short acknowledgment and use <workflow_manage_confirmed> — " \
                           "do NOT re-summarize or show another <workflow_manage>.]"
            elif msg_type == "workflow_run_request":
                wf_name = m.metadata_json.get("workflow_name", "")
                content += f"\n\n[System: A confirmation card to run '{wf_name}' is being shown. " \
                           "When they confirm, respond with a short acknowledgment and use <workflow_run_confirmed> — " \
                           "do NOT re-summarize or show another <workflow_run>.]"
            elif msg_type == "workflow_run_result":
                success = m.metadata_json.get("success", False)
                wf_name = m.metadata_json.get("workflow_name", "")
                steps = m.metadata_json.get("steps_executed", 0)
                if success:
                    content += f"\n\n[System: Workflow '{wf_name}' ran successfully — {steps} step(s) completed.]"
                else:
                    error = m.metadata_json.get("error", "")
                    content += f"\n\n[System: Workflow '{wf_name}' failed. Error: {error}]"
            elif msg_type == "workflow_schedule_request":
                wf_name = m.metadata_json.get("workflow_name", "")
                content += f"\n\n[System: A confirmation card to change the schedule of '{wf_name}' is being shown. " \
                           "When they confirm, respond with a short acknowledgment and use <workflow_schedule_confirmed> — " \
                           "do NOT re-summarize or show another <workflow_schedule>.]"
            elif msg_type == "workflow_schedule_result":
                success = m.metadata_json.get("success", False)
                wf_name = m.metadata_json.get("workflow_name", "")
                if success:
                    new_sched = m.metadata_json.get("new_schedule", "")
                    content += f"\n\n[System: Schedule for '{wf_name}' was updated to: {new_sched}.]"
                else:
                    error = m.metadata_json.get("error", "")
                    content += f"\n\n[System: Failed to update schedule for '{wf_name}'. Error: {error}]"
            elif msg_type == "workflow_list":
                wfs = m.metadata_json.get("workflows", [])
                content += f"\n\n[System: Workflow list was shown to user — {len(wfs)} workflow(s).]"
            elif msg_type == "workflow_activity":
                acts = m.metadata_json.get("activity", [])
                content += f"\n\n[System: Activity summary was shown — {len(acts)} recent entries.]"
            elif msg_type == "workflow_status":
                wf = m.metadata_json.get("workflow", {})
                logs = m.metadata_json.get("recent_activity", [])
                content += f"\n\n[System: Status for '{wf.get('name', '')}' was shown — {len(logs)} recent activity entries.]"
        messages.append({"role": m.role, "content": content})

    # Get AI response and parse for signal tags
    tz = request.timezone or "UTC"
    all_workflows = db.query(Workflow).all()
    wf_names = [w.name for w in all_workflows] if all_workflows else None

    # Query integration connection status for dynamic prompt
    connected_integrations = db.query(Integration).filter(
        Integration.status == "connected"
    ).all()
    connected_providers = [i.provider for i in connected_integrations]

    raw_content = await get_ai_response(
        messages, timezone=tz, workflow_names=wf_names,
        connected_providers=connected_providers,
    )
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

    # ── Workflow queries (list, status, activity, run) ────────────────
    # These must be handled BEFORE the action-gathering safety net, which can
    # false-positive on words like "schedule" or "calendar" in workflow descriptions.
    if signals["workflow_list"]:
        wf_data = []
        for w in all_workflows:
            wf_data.append({
                "id": w.id,
                "name": w.name,
                "status": w.status,
                "description": w.description,
                "trigger_type": w.trigger_type,
                "step_count": len(w.steps) if w.steps else 0,
                "updated_at": w.updated_at.isoformat() if w.updated_at else None,
            })
        metadata = {
            "message_type": "workflow_list",
            "workflows": wf_data,
        }

    if signals["workflow_status"]:
        wf_name = signals["workflow_status"]
        matched = match_workflow_by_name(all_workflows, wf_name)
        if matched:
            recent_logs = db.query(ActivityLog).filter(
                ActivityLog.workflow_id == matched.id
            ).order_by(ActivityLog.created_at.desc()).limit(10).all()
            log_data = []
            for log in recent_logs:
                log_data.append({
                    "action_type": log.action_type,
                    "description": log.description,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                    "details": log.details,
                })
            metadata = {
                "message_type": "workflow_status",
                "workflow": {
                    "id": matched.id,
                    "name": matched.name,
                    "status": matched.status,
                    "description": matched.description,
                    "trigger_type": matched.trigger_type,
                    "step_count": len(matched.steps) if matched.steps else 0,
                    "updated_at": matched.updated_at.isoformat() if matched.updated_at else None,
                },
                "recent_activity": log_data,
            }
        else:
            metadata = {
                "message_type": "workflow_manage_not_found",
                "manage_action": "check status of",
                "query": wf_name,
            }

    if signals["workflow_activity"]:
        recent_logs = db.query(ActivityLog).order_by(
            ActivityLog.created_at.desc()
        ).limit(20).all()
        log_data = []
        for log in recent_logs:
            log_data.append({
                "action_type": log.action_type,
                "description": log.description,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "workflow_id": log.workflow_id,
            })
        metadata = {
            "message_type": "workflow_activity",
            "activity": log_data,
        }

    if signals["workflow_run"]:
        wf_name = signals["workflow_run"]
        matched = match_workflow_by_name(all_workflows, wf_name)
        if matched:
            metadata = {
                "message_type": "workflow_run_request",
                "workflow_id": matched.id,
                "workflow_name": matched.name,
                "workflow_status": matched.status,
                "step_count": len(matched.steps) if matched.steps else 0,
            }
        else:
            metadata = {
                "message_type": "workflow_manage_not_found",
                "manage_action": "run",
                "query": wf_name,
            }

    if signals["workflow_run_confirmed"]:
        wf_name = signals["workflow_run_confirmed"]
        prior = _find_latest_run_request(db, conversation.id)
        wf_id = prior.get("workflow_id") if prior else None

        if not wf_id:
            matched = match_workflow_by_name(all_workflows, wf_name)
            wf_id = matched.id if matched else None

        if wf_id:
            wf = db.query(Workflow).filter(Workflow.id == wf_id).first()
            if wf and wf.status != "paused" and wf.steps:
                context = await extract_run_context_from_conversation(messages, timezone=tz)
                results = await run_workflow(db, wf, context)
                all_success = all(r["status"] == "success" for r in results)
                metadata = {
                    "message_type": "workflow_run_result",
                    "workflow_name": wf.name,
                    "success": all_success,
                    "steps_executed": len(results),
                    "results": results,
                }
            elif wf and wf.status == "paused":
                metadata = {
                    "message_type": "workflow_run_result",
                    "workflow_name": wf.name if wf else wf_name,
                    "success": False,
                    "steps_executed": 0,
                    "results": [],
                    "error": "This workflow is paused — resume it first.",
                }
            else:
                metadata = {
                    "message_type": "workflow_run_result",
                    "workflow_name": wf.name if wf else wf_name,
                    "success": False,
                    "steps_executed": 0,
                    "results": [],
                    "error": "Workflow has no steps to execute.",
                }
        else:
            metadata = {
                "message_type": "workflow_run_result",
                "workflow_name": wf_name,
                "success": False,
                "steps_executed": 0,
                "results": [],
                "error": "Could not find that workflow.",
            }

    # ── Schedule management (set / change schedule) ──────────────────────
    if signals["workflow_schedule"]:
        wf_name = signals["workflow_schedule"]
        matched = match_workflow_by_name(all_workflows, wf_name)
        if matched:
            metadata = {
                "message_type": "workflow_schedule_request",
                "workflow_id": matched.id,
                "workflow_name": matched.name,
                "workflow_status": matched.status,
                "current_schedule": (matched.trigger_config or {}).get("schedule", "None"),
            }
        else:
            metadata = {
                "message_type": "workflow_manage_not_found",
                "manage_action": "change schedule of",
                "query": wf_name,
            }

    if signals["workflow_schedule_confirmed"]:
        wf_name = signals["workflow_schedule_confirmed"]
        prior = _find_latest_schedule_request(db, conversation.id)
        wf_id = prior.get("workflow_id") if prior else None

        if not wf_id:
            matched = match_workflow_by_name(all_workflows, wf_name)
            wf_id = matched.id if matched else None

        if wf_id:
            wf = db.query(Workflow).filter(Workflow.id == wf_id).first()
            if wf:
                # Extract the new schedule from the conversation
                schedule_data = await extract_schedule_from_conversation(messages, timezone=tz)
                if schedule_data:
                    # Update trigger_config
                    new_config = dict(wf.trigger_config or {})
                    new_config["cron_expression"] = schedule_data["cron_expression"]
                    new_config["schedule"] = schedule_data["schedule_description"]
                    new_config["frequency"] = schedule_data["frequency"]
                    new_config["timezone"] = tz
                    wf.trigger_config = new_config
                    wf.trigger_type = "schedule"
                    wf.updated_at = datetime.now(timezone.utc)

                    # Recompute next_run_at
                    from app.services.scheduler import update_next_run
                    update_next_run(db, wf)

                    # Log to activity
                    log_entry = ActivityLog(
                        workflow_id=wf.id,
                        action_type="schedule_updated",
                        description=f"Schedule for '{wf.name}' updated to: {schedule_data['schedule_description']}",
                        details={
                            "cron_expression": schedule_data["cron_expression"],
                            "schedule": schedule_data["schedule_description"],
                            "source": "chat",
                        },
                    )
                    db.add(log_entry)
                    db.commit()

                    metadata = {
                        "message_type": "workflow_schedule_result",
                        "success": True,
                        "workflow_name": wf.name,
                        "new_schedule": schedule_data["schedule_description"],
                        "next_run_at": wf.next_run_at.isoformat() if wf.next_run_at else None,
                    }
                else:
                    metadata = {
                        "message_type": "workflow_schedule_result",
                        "success": False,
                        "workflow_name": wf.name,
                        "error": "Could not understand the new schedule.",
                    }
            else:
                metadata = {
                    "message_type": "workflow_schedule_result",
                    "success": False,
                    "workflow_name": wf_name,
                    "error": "Could not find that workflow.",
                }
        else:
            metadata = {
                "message_type": "workflow_schedule_result",
                "success": False,
                "workflow_name": wf_name,
                "error": "Could not find that workflow.",
            }

    # Detect action request — from tag or from response content as fallback
    action_request_type = signals["action_request"] or _detect_action_from_content(clean_content)

    # Map action types to the provider they require
    ACTION_PROVIDER = {
        "send_email": "gmail",
        "create_event": "google_calendar",
        "update_event": "google_calendar",
        "check_availability": "google_calendar",
        "list_events": "google_calendar",
    }

    # Safety net: if the AI is gathering fields for a disconnected tool
    # (asking for subject, time, etc. without emitting a connect_tool tag),
    # intercept and show a connect card instead.
    if not action_request_type and not signals.get("connect_tool") and not metadata:
        gathering_action = _detect_action_gathering(clean_content)
        if gathering_action:
            required_provider = ACTION_PROVIDER.get(gathering_action)
            if required_provider and required_provider not in connected_providers:
                provider_name = "Gmail" if required_provider == "gmail" else "Google Calendar"
                clean_content = (
                    f"To do that, we'll need to connect your {provider_name} first. "
                    "Click below to get that set up — it only takes a moment!"
                )
                metadata = {
                    "message_type": "connect_tool",
                    "provider": required_provider,
                }

    if action_request_type:
        # Check if the required tool is connected before proceeding
        required_provider = ACTION_PROVIDER.get(action_request_type)
        if required_provider and required_provider not in connected_providers:
            # Tool not connected — show connect card instead of action card
            provider_name = "Gmail" if required_provider == "gmail" else "Google Calendar"
            clean_content = (
                f"To do that, we'll need to connect your {provider_name} first. "
                "Click below to get that set up — it only takes a moment!"
            )
            metadata = {
                "message_type": "connect_tool",
                "provider": required_provider,
            }
        else:
            # Extract structured action parameters via a second Claude call
            params = await extract_action_from_conversation(messages, action_request_type, timezone=tz)

            # Read-only actions execute immediately — no confirmation needed
            if action_request_type in ("list_events", "check_availability"):
                exec_meta = {"action_type": action_request_type, "action_params": params or {}}
                result = await _execute_chat_action(db, exec_meta, conversation_id=conversation.id)
                metadata = {
                    "message_type": "action_result",
                    "action_type": action_request_type,
                    "success": result["status"] == "success",
                    "details": result.get("details", {}),
                }
            else:
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
            # Guard: check if required tool is connected before executing
            required_provider = ACTION_PROVIDER.get(action_type)
            if required_provider and required_provider not in connected_providers:
                provider_name = "Gmail" if required_provider == "gmail" else "Google Calendar"
                clean_content = (
                    f"Hmm, it looks like your {provider_name} isn't connected yet. "
                    "Let's get that set up first!"
                )
                metadata = {
                    "message_type": "connect_tool",
                    "provider": required_provider,
                }
            else:
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

    # ── Tool connections (connect / disconnect) ────────────────────────
    if signals["connect_tool"]:
        provider = signals["connect_tool"]
        valid_providers = {"gmail", "google_calendar"}
        if provider in valid_providers:
            already = provider in connected_providers
            if already:
                # AI shouldn't emit this, but handle gracefully
                metadata = {
                    "message_type": "connect_already",
                    "provider": provider,
                }
            else:
                metadata = {
                    "message_type": "connect_tool",
                    "provider": provider,
                }

    if signals["disconnect_tool"]:
        provider = signals["disconnect_tool"]
        metadata = {
            "message_type": "disconnect_request",
            "provider": provider,
        }

    if signals["disconnect_confirmed"]:
        provider = signals["disconnect_confirmed"]
        try:
            from app.routers.integrations import _disconnect
            _disconnect(provider, db)
            metadata = {
                "message_type": "disconnect_result",
                "provider": provider,
                "success": True,
            }
            # Log the disconnection
            provider_name = "Gmail" if provider == "gmail" else "Google Calendar"
            log = ActivityLog(
                action_type="tool_disconnected",
                description=f"{provider_name} disconnected via chat",
                details={"provider": provider, "source": "chat"},
            )
            db.add(log)
        except Exception as e:
            metadata = {
                "message_type": "disconnect_result",
                "provider": provider,
                "success": False,
                "error": str(e),
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


def _detect_action_gathering(content: str) -> Optional[str]:
    """Detect if the AI is engaging with an action request instead of suggesting connection.

    Catches any response where the AI is proceeding with an email or calendar task
    (gathering fields, offering choices, disambiguating) without suggesting a tool connection.
    """
    lower = content.lower()
    # Must contain a question — the AI is asking the user something
    if "?" not in lower:
        return None
    # Email: any response that engages with sending email
    email_signals = [
        "subject", "body", "email say", "email should", "send that email",
        "send an email", "send the email", "draft", "write the email",
        "who should i", "who do you want", "recipient", "send it to",
    ]
    if any(s in lower for s in email_signals):
        return "send_email"
    # Calendar: any response that engages with calendar/scheduling
    cal_signals = [
        "event", "meeting", "appointment", "schedule", "put on your calendar",
        "add to your calendar", "block off", "what time", "how long should",
        "your calendar", "time slot", "availability", "available",
        "what's on", "show you", "check if", "free", "busy",
    ]
    if any(s in lower for s in cal_signals):
        return "check_availability"
    return None


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
            recipient = params["recipient"]
            cc = params.get("cc")
            bcc = params.get("bcc")
            result = send_email(db, recipient, params["subject"], params["body"], cc=cc, bcc=bcc)
            # Build human-readable recipient description
            to_str = ", ".join(recipient) if isinstance(recipient, list) else recipient
            description = f"Sent email to {to_str}: {params['subject']}"
            details = {
                "recipient": recipient,
                "subject": params["subject"],
                "gmail_message_id": result.get("message_id"),
                "source": "chat",
            }
            if cc:
                details["cc"] = cc
            if bcc:
                details["bcc"] = bcc

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
            events = list_upcoming_events(
                db,
                max_results=10,
                time_min=params.get("time_min"),
                time_max=params.get("time_max"),
            )
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


def _find_latest_run_request(db: Session, conversation_id: int) -> Optional[dict]:
    """Find the most recent workflow_run_request metadata in this conversation."""
    msgs = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.role == "assistant",
    ).order_by(Message.created_at.desc()).all()

    for msg in msgs:
        if msg.metadata_json and isinstance(msg.metadata_json, dict):
            if msg.metadata_json.get("message_type") == "workflow_run_request":
                return msg.metadata_json
    return None


def _find_latest_schedule_request(db: Session, conversation_id: int) -> Optional[dict]:
    """Find the most recent workflow_schedule_request metadata in this conversation."""
    msgs = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.role == "assistant",
    ).order_by(Message.created_at.desc()).all()

    for msg in msgs:
        if msg.metadata_json and isinstance(msg.metadata_json, dict):
            if msg.metadata_json.get("message_type") == "workflow_schedule_request":
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

    # Sync next_run_at for scheduled workflows
    if new_status == "active" and workflow.trigger_type == "schedule":
        from app.services.scheduler import update_next_run
        update_next_run(db, workflow)
    elif new_status == "paused":
        workflow.next_run_at = None

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


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    # Detach any workflows that were created from this conversation
    db.query(Workflow).filter(Workflow.conversation_id == conversation_id).update(
        {"conversation_id": None}
    )
    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.delete(conversation)
    db.commit()
    return {"status": "deleted", "id": conversation_id}


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
