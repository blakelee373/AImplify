# AImplify - Project Instructions

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
- Current tags: `action_request`, `action_confirmed`, `workflow_ready`, `workflow_confirmed`, `workflow_manage`, `workflow_manage_confirmed`, `connect_tool`, `disconnect_tool`, `disconnect_confirmed`
- New action types must be added to: `ACTION_EXTRACTION_TOOLS` (ai_engine.py), `ACTION_PROVIDER` map (chat.py), `_execute_chat_action` (chat.py), `ACTION_LABELS` (MessageBubble.tsx)

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
