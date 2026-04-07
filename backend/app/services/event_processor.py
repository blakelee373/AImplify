"""Async event processing queue with retry logic."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.database import SessionLocal
from app.models.business_event import BusinessEvent
from app.services.event_bus import get_matching_workflows
from app.services.deduplication import is_duplicate, record_execution
from app.services.condition_engine import evaluate_conditions
from app.services.workflow_executor import execute_workflow
from app.services.variable_resolver import build_context_from_event

logger = logging.getLogger(__name__)

# In-memory queue (upgrade to Redis for production)
_event_queue: asyncio.Queue = asyncio.Queue()

# Retry delays in seconds: 60s, 300s, 900s
RETRY_DELAYS = [60, 300, 900]


async def enqueue_event(event_id: str):
    """Add an event ID to the processing queue."""
    await _event_queue.put(event_id)


async def process_pending_events():
    """Process any unprocessed events from the database (for restart recovery)."""
    db = SessionLocal()
    try:
        pending = (
            db.query(BusinessEvent)
            .filter(
                BusinessEvent.processed == False,  # noqa: E712
                BusinessEvent.retry_count < BusinessEvent.max_retries,
            )
            .order_by(BusinessEvent.created_at)
            .limit(50)
            .all()
        )
        for event in pending:
            await _event_queue.put(event.id)
        if pending:
            logger.info("Recovered %d pending events from database", len(pending))
    finally:
        db.close()


async def event_worker():
    """Background worker that continuously processes events from the queue."""
    while True:
        try:
            event_id = await _event_queue.get()
            await _process_single_event(event_id)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Event worker error: %s", e)
            await asyncio.sleep(1)


async def _process_single_event(event_id: str):
    """Process one event: find matching workflows, evaluate conditions, execute."""
    db = SessionLocal()
    try:
        event = db.query(BusinessEvent).filter(BusinessEvent.id == event_id).first()
        if not event or event.processed:
            return

        payload = event.payload or {}
        matching = get_matching_workflows(event.event_type)

        if not matching:
            event.processed = True
            event.processed_at = datetime.now(timezone.utc)
            db.commit()
            return

        all_succeeded = True

        for wf_info in matching:
            workflow_id = wf_info["id"]

            # Deduplication check
            if is_duplicate(workflow_id, event_id):
                logger.debug("Skipping duplicate: workflow=%s event=%s", workflow_id, event_id)
                continue

            # Build context from event payload
            context = build_context_from_event(payload, payload.get("business_data"))
            context["event_type"] = event.event_type
            context["event_id"] = event_id

            # Evaluate conditions
            conditions = wf_info.get("conditions") or []
            if conditions and not evaluate_conditions(conditions, context):
                logger.info("Conditions not met for workflow '%s', skipping", wf_info["name"])
                continue

            # Execute
            dry_run = wf_info["status"] == "testing"
            try:
                result = await execute_workflow(
                    workflow_id=workflow_id,
                    trigger_context=context,
                    dry_run=dry_run,
                    trigger_event_id=event_id,
                )
                record_execution(workflow_id, event_id)

                if not result.get("success"):
                    all_succeeded = False

            except Exception as e:
                logger.error("Execution failed for workflow %s: %s", workflow_id, e)
                all_succeeded = False

        if all_succeeded:
            event.processed = True
            event.processed_at = datetime.now(timezone.utc)
        else:
            event.retry_count += 1
            if event.retry_count >= event.max_retries:
                event.processed = True  # give up
                event.processed_at = datetime.now(timezone.utc)
                logger.warning("Event %s exceeded max retries", event_id)
            else:
                # Re-queue with delay
                delay = RETRY_DELAYS[min(event.retry_count - 1, len(RETRY_DELAYS) - 1)]
                asyncio.get_event_loop().call_later(
                    delay, lambda eid=event_id: asyncio.ensure_future(enqueue_event(eid))
                )

        db.commit()

    except Exception as e:
        logger.error("Event processing error for %s: %s", event_id, e)
    finally:
        db.close()
