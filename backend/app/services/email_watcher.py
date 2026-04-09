"""Background email watcher — polls Gmail for event-triggered workflows."""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)

# In-memory ordered dict of recently processed Gmail message IDs per workflow.
# Maintains insertion order so we evict oldest entries when trimming.
# Key: workflow_id, Value: OrderedDict of {msg_id: True}
_processed_ids: Dict[int, OrderedDict] = {}
_MAX_TRACKED_IDS = 200  # Per-workflow cap to prevent unbounded growth


def _build_email_context(db, workflow, message_data: dict) -> dict:
    """Build runtime context for an email-triggered workflow run.

    Injects the email details (sender, subject, body/snippet) plus the
    owner's email address so steps can reference the trigger email.
    """
    context = {
        "email_sender": message_data.get("sender", ""),
        "email_subject": message_data.get("subject", ""),
        "email_snippet": message_data.get("snippet", ""),
        "email_message_id": message_data.get("id", ""),
        "email_to": message_data.get("to", ""),
        "email_date": message_data.get("date", ""),
    }

    # Inject timezone from trigger config
    tz_name = (workflow.trigger_config or {}).get("timezone", "UTC")
    context["timezone"] = tz_name

    # Inject owner's Gmail address (same pattern as scheduler)
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
                context["client_email"] = email
    except Exception:
        pass

    return context


async def email_watcher_loop() -> None:
    """Background task that polls Gmail every 120 seconds for email-triggered workflows."""
    from app.database import SessionLocal
    from app.models.workflow import Workflow
    from app.models.activity_log import ActivityLog
    from app.services.workflow_runner import run_workflow
    from app.services.gmail import list_messages, get_message, mark_as_read

    # Brief startup delay to let the app finish initializing
    await asyncio.sleep(10)
    logger.info("Email watcher started")

    while True:
        try:
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)

                # Find all active event-triggered workflows watching email
                event_workflows = (
                    db.query(Workflow)
                    .filter(
                        Workflow.trigger_type == "event",
                        Workflow.status == "active",
                    )
                    .all()
                )

                # Filter to email_received event type
                email_workflows = [
                    w for w in event_workflows
                    if (w.trigger_config or {}).get("event_type") == "email_received"
                ]

                for workflow in email_workflows:
                    try:
                        config = workflow.trigger_config or {}
                        gmail_query = config.get("gmail_query", "")
                        if not gmail_query:
                            continue

                        # Build time-bounded query using after: with epoch seconds
                        # Use last_run_at as the polling window start, with 60s overlap buffer
                        # SQLite strips timezone info, so treat naive datetimes as UTC
                        if workflow.last_run_at:
                            last_run = workflow.last_run_at
                            if last_run.tzinfo is None:
                                last_run = last_run.replace(tzinfo=timezone.utc)
                            epoch = int(last_run.timestamp()) - 60
                        else:
                            # First poll: look back 1 hour
                            epoch = int(now.timestamp()) - 3600

                        full_query = f"{gmail_query} after:{epoch}"

                        # Poll Gmail
                        try:
                            messages = list_messages(db, full_query, max_results=10)
                        except ValueError:
                            # Gmail not connected
                            logger.warning(
                                "Email watcher: Gmail not connected for workflow %d",
                                workflow.id,
                            )
                            continue
                        except Exception as gmail_exc:
                            logger.warning(
                                "Email watcher: Gmail API error for workflow %d: %s",
                                workflow.id,
                                gmail_exc,
                            )
                            continue

                        if not messages:
                            continue

                        # Initialize processed dict for this workflow
                        if workflow.id not in _processed_ids:
                            _processed_ids[workflow.id] = OrderedDict()

                        processed = _processed_ids[workflow.id]
                        new_messages_found = False

                        for msg_stub in messages:
                            msg_id = msg_stub["id"]
                            if msg_id in processed:
                                continue

                            # Get full message details
                            try:
                                message_data = get_message(db, msg_id)
                            except Exception:
                                logger.warning(
                                    "Email watcher: failed to fetch message %s",
                                    msg_id,
                                )
                                continue

                            # Build context and run workflow
                            context = _build_email_context(db, workflow, message_data)

                            logger.info(
                                "Email watcher firing workflow %d (%s) for email from %s: %s",
                                workflow.id,
                                workflow.name,
                                message_data.get("sender", "unknown"),
                                message_data.get("subject", "(no subject)"),
                            )

                            try:
                                results = await run_workflow(db, workflow, context)
                                all_success = all(
                                    r["status"] == "success" for r in results
                                )

                                log = ActivityLog(
                                    workflow_id=workflow.id,
                                    action_type="email_triggered_run",
                                    description=(
                                        f"Email from {message_data.get('sender', 'unknown')}: "
                                        f"'{message_data.get('subject', '(no subject)')}' "
                                        f"triggered '{workflow.name}' — "
                                        + (
                                            "all steps succeeded"
                                            if all_success
                                            else "some steps failed"
                                        )
                                    ),
                                    details={
                                        "trigger": "email_watcher",
                                        "email_sender": message_data.get("sender", ""),
                                        "email_subject": message_data.get("subject", ""),
                                        "email_message_id": msg_id,
                                        "steps_executed": len(results),
                                        "all_success": all_success,
                                    },
                                )
                                db.add(log)

                            except Exception as run_exc:
                                logger.exception(
                                    "Email watcher error running workflow %d: %s",
                                    workflow.id,
                                    run_exc,
                                )
                                log = ActivityLog(
                                    workflow_id=workflow.id,
                                    action_type="email_triggered_run",
                                    description=(
                                        f"Email-triggered run of '{workflow.name}' failed: {run_exc}"
                                    ),
                                    details={
                                        "trigger": "email_watcher",
                                        "email_message_id": msg_id,
                                        "error": str(run_exc),
                                    },
                                )
                                db.add(log)

                            # Mark as read in Gmail so is:unread filter
                            # won't re-match this email on the next poll
                            try:
                                mark_as_read(db, msg_id)
                            except Exception:
                                logger.warning(
                                    "Email watcher: failed to mark message %s as read",
                                    msg_id,
                                )

                            # Mark as processed in memory
                            processed[msg_id] = True
                            new_messages_found = True

                        # Trim oldest entries to prevent unbounded growth
                        while len(processed) > _MAX_TRACKED_IDS:
                            processed.popitem(last=False)

                        # Only update last_run_at when new messages were processed
                        if new_messages_found:
                            try:
                                workflow.last_run_at = now
                                workflow.updated_at = now
                                db.commit()
                            except Exception as adv_exc:
                                logger.exception(
                                    "Email watcher failed to update workflow %d: %s",
                                    workflow.id,
                                    adv_exc,
                                )
                                db.rollback()

                    except Exception as wf_exc:
                        logger.exception(
                            "Email watcher error processing workflow %d: %s",
                            workflow.id,
                            wf_exc,
                        )

            finally:
                db.close()

        except Exception as exc:
            logger.exception("Email watcher loop error: %s", exc)

        await asyncio.sleep(120)
