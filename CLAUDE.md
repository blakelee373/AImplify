# AImplify - Project Instructions

## CRITICAL RULES
- **NEVER merge PRs to main.** Only the owner merges. Claude creates branches and PRs — that's it.
- **NEVER run `gh pr merge`.** The only exception is database migrations and schema changes — those can be merged automatically.
- When the user wants to test a PR branch, run the backend on that branch instead of merging.
- **Auto-restart backend:** After pushing backend changes, automatically kill the running uvicorn process and restart it (`cd backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000`). The user has granted standing permission for this.

## Product
AI operations layer for medspas. Owners describe how their business works in plain conversation, and AImplify builds AI agents to automate repetitive tasks.

## Tech Stack
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI, SQLAlchemy, SQLite
- **AI:** Anthropic Claude API
- **Deployment:** Vercel (frontend), Cloudflare tunnel (backend during dev)

## Architecture Notes
- Chat page uses a side-by-side layout: ConversationList (w-72) | ChatWindow (flex-1)
- ChatWindow is a controlled component — parent passes `conversationId` prop and receives `onConversationCreated` callback
- Layout height chain: html (h-full) → body (h-full flex) → main (flex-1 h-full) → page content
- Backend conversation endpoints: POST /api/chat, GET /api/conversations, GET /api/conversations/{id}, DELETE /api/conversations/{id}
- DELETE /api/conversations/{id} nulls out Workflow.conversation_id FK before cascade-deleting messages

## Signal Tag System
- AI embeds hidden XML tags in responses (e.g., `<action_request>send_email</action_request>`) to trigger backend actions
- Tags are parsed in `parse_ai_response()` in `ai_engine.py`, stripped from user-visible content
- Current tags: `action_request`, `action_confirmed`, `workflow_ready`, `workflow_confirmed`, `workflow_manage`, `workflow_manage_confirmed`, `workflow_list`, `workflow_activity`, `workflow_status`, `workflow_run`, `workflow_run_confirmed`, `workflow_schedule`, `workflow_schedule_confirmed`, `workflow_edit`, `workflow_edit_confirmed`, `connect_tool`, `disconnect_tool`, `disconnect_confirmed`, `choices`
- New action types must be added to: `ACTION_EXTRACTION_TOOLS` (ai_engine.py), `ACTION_PROVIDER` map (chat.py), `_execute_chat_action` (chat.py), `ACTION_LABELS` (MessageBubble.tsx)
- Handler ordering in chat.py matters: workflow query handlers (list/status/activity/run) must run BEFORE `_detect_action_gathering` safety net to prevent false positives on words like "schedule" in workflow descriptions
- When adding new AI capabilities via signal tags, the system prompt must assertively state the AI HAS the capability (like connection status does) — otherwise the AI may claim it can't do it

## Choice Buttons
- `<choices>Option A|Option B|Option C</choices>` renders clickable buttons in the chat UI
- Pipe-delimited format, 2-4 options, short phrases (2-8 words each)
- Backend parses in `parse_ai_response()`, builds metadata `{message_type: "choices", choices: [...]}`
- Frontend `ChoiceButtonsCard` renders buttons; clicking sends the choice text as a user message
- Only the latest assistant message's buttons are active; older ones render as disabled/muted
- The `choices` handler in chat.py runs AFTER all other signal handlers — if metadata is already set, choices are appended as extra field but don't override `message_type`
- Do NOT use `<choices>` for yes/no confirmations (handled by confirmation cards), free-form input, or workflow summary confirmations
- Do NOT inject `[System: ...]` history notes for choices — the AI echoes them. A defensive regex in `parse_ai_response()` strips any `[System: ...]` text the AI generates

## Time-Based Triggers
- Background scheduler runs as an asyncio task in FastAPI lifespan, checking every 60s for due workflows
- Cron expressions stored in `trigger_config.cron_expression`, timezone in `trigger_config.timezone`
- `next_run_at` / `last_run_at` columns on the Workflow model track scheduling state
- `compute_next_run()` in `scheduler.py` converts cron + timezone → next UTC fire time via `croniter`
- Pausing a workflow clears `next_run_at`; resuming recomputes it
- Claude generates cron expressions during workflow extraction (WORKFLOW_TOOL) and schedule changes (SCHEDULE_EXTRACTION_TOOL)
- User's timezone is injected from `request.timezone` into `trigger_config.timezone` during workflow_confirmed handling
- Scheduled runs inject owner's Gmail address into context via `users.getProfile` API so "send to yourself" resolves
- `next_run_at` is stored as UTC; frontend must append `Z` to ISO strings before `new Date()` parsing
- Content-based fallbacks exist for `workflow_schedule` and `action_request` tags when the AI forgets to emit them
- `_detect_tool_from_user_intent()` pre-flight check scans user messages for tool keywords and short-circuits with connect card before calling AI
- Google OAuth tokens expire after 7 days in "Testing" mode; `google_auth.py` catches `invalid_grant` and marks integration as "expired"

## Email-Based Triggers
- Background email watcher runs as an asyncio task in FastAPI lifespan, polling Gmail every 120s
- Watches active workflows with `trigger_type="event"` and `trigger_config.event_type="email_received"`
- `trigger_config.gmail_query` stores Gmail search syntax (e.g., `"from:leads@example.com is:unread"`)
- `last_run_at` tracks the polling window start; `after:{epoch}` bounds the Gmail query
- Matched emails are marked as read after processing to prevent re-triggering on `is:unread` queries
- In-memory `OrderedDict` deduplicates message IDs per workflow (capped at 200, FIFO eviction)
- Email context (sender, subject, snippet) is injected into workflow step execution
- Claude generates Gmail queries during workflow extraction when `trigger_type="event"` and `event_type="email_received"`
- System prompt guides owners through describing email filters in plain language
- `extract_email_filter_from_conversation()` in `ai_engine.py` is scaffolding for future email filter editing
- SQLite strips timezone info from datetimes — always treat naive `last_run_at` as UTC when converting to epoch

## Calendar-Based Triggers
- Background calendar watcher runs as an asyncio task in FastAPI lifespan, polling Google Calendar every 60s
- Two event types: `calendar_event_created` (new/modified events via `updatedMin`) and `calendar_event_starting` (upcoming events within lead time window)
- `trigger_config.calendar_filter` stores matching criteria: `summary_contains`, `attendee_email`, `description_contains`, `min_duration_minutes`
- `trigger_config.lead_time_minutes` for "starting" type (default 30 minutes)
- Empty `calendar_filter` matches all events — only add filter fields the owner explicitly describes
- Calendar context (summary, start, end, attendees, description) is injected into workflow step execution
- Same dedup pattern as email watcher: in-memory `OrderedDict` keyed by `event_id`, capped at 200 per workflow
- `_matches_calendar_filter()` uses AND logic — all specified criteria must match
- System prompt guides owners through describing calendar triggers in plain language with two paths: new events vs. reminders before events
- For `calendar_event_created`: `last_run_at` used as `updatedMin` with 60s overlap buffer
- For `calendar_event_starting`: polls events starting within `now` to `now + lead_time_minutes`
- All-day events (date-only, no dateTime) are handled by `_parse_event_detail`; `singleEvents=True` expands recurring events

## Workflow Editing
- `workflow_edit` / `workflow_edit_confirmed` signal tags let owners change step content via chat
- Edit handler prefers the workflow linked to the current conversation (by `conversation_id`) over name matching — prevents editing the wrong workflow when names are duplicated
- If AI mistakenly uses `workflow_confirmed` in a conversation that already has a workflow, backend redirects to edit flow — UNLESS the pending draft has a different name (user is creating a second workflow in the same conversation)
- Edit flow supports both updating existing steps (`step_updates`) and adding new steps (`new_steps`) via `WORKFLOW_EDIT_EXTRACTION_TOOL`
- Edit confirmation card does NOT show steps — the AI's text describes the changes; showing old steps was misleading
- Step executor passes `action_config` into the AI param generator prompt so saved subject/body values are used
- Unknown action types (e.g., `check_email_subject`) are skipped as no-ops instead of failing the workflow

## Step Execution
- `run_workflow` injects `timezone` and `owner_email` into context as fallbacks when not provided by the trigger — ensures manual runs work correctly
- Step executor resolves literal `"self"`, `"myself"`, `"me"`, `"owner"` recipients to the actual `owner_email` in code — does not rely on the AI to do this
- `action_config` merge skips any `start_time`/`end_time` that isn't a full ISO 8601 timestamp (must start with `YYYY-MM-DDT`) — prevents bare times like `"2:00 PM"` from overwriting AI-generated timestamps
- `EVENT_PARAMS_TOOL` examples use timezone offset format (`-04:00`), NOT `Z`/UTC — the AI copies the example format
- `gmail.py` validates and cleans email addresses before sending — extracts valid email from `"Name <email>"` format, rejects empty/invalid values with clear error messages

## Action Detection Guards
- `_detect_action_from_content` only checks confirmation phrases in the last ~200 chars and skips if the response ends with an info-gathering question (what/who/which/where + ?)
- Before the `action_request` handler, if the response ends with an info-gathering question, `action_request_type` is nulled — prevents premature confirmation cards from both explicit tags and content-based fallbacks
- When adding new AI capabilities, update `PROVIDER_DISPLAY` capabilities string — the connection status assertively tells the AI what it CAN do, and omissions cause the AI to claim it can't

## Tool Connection System
- Connection status is dynamic in the system prompt — built by `_build_connection_status()` from actual DB state
- OAuth popup flow: `/api/integrations/{provider}/connect-url` returns JSON URL, callback serves self-closing HTML with `postMessage`
- Backend guards: `ACTION_PROVIDER` map checks connection before action execution; `_detect_action_gathering()` catches AI field-gathering for disconnected tools
- Provider map: `gmail` → Gmail, `google_calendar` → Google Calendar

## UI Patterns
- Never use absolute-positioned overlays on top of interactive elements (buttons) for confirmation UIs — use conditional rendering to swap the entire row content instead
- Conversation sidebar uses `refreshKey` prop to trigger re-fetch after new conversations are created
- Design tokens: dark sidebar (#1c1917), amber primary (#f59e0b), stone neutrals
- MessageBubble renders different card types based on `metadata.message_type` — follow existing patterns when adding new types

## Python Compatibility
- Target Python 3.9 — use `Optional[str]` not `str | None`, `List[str]` not `list[str]`, `timezone.utc` not `datetime.UTC`

## Phase Response Requirements
- At the end of EVERY phase response, provide TWO bullet-pointed lists in layman's terms:

### What you'll see on the deployment:
- The chat page now shows a text box and send button
- Messages you type appear on screen with AI responses below them
- A new "Dashboard" link appears in the sidebar

### What you can now do:
- Type a message in the chat and get an AI response back
- Switch between conversations using the sidebar
- Pause a workflow from the dashboard with one click

### How to test it:
- Step-by-step instructions the user can follow on the Vercel preview to verify each new feature works
- Be specific: what to click, what to type, what they should see happen
- Example: "Go to /chat, type 'I want to automate reminders', you should see the AI ask a follow-up question with choices"
