# Phase 18D: Transparent State & Business Memory

## Overview

Three-tier memory system that lets AImplify remember business context across conversations with full owner control.

## Memory Tiers

| Tier | Scope | Storage | Lifecycle |
|------|-------|---------|-----------|
| 1 — Transient | Single exchange | Signal tags + metadata | Auto-cleared after response |
| 2 — Session | Conversation | `conversations.session_context` (JSON) | Per-conversation, cleared on end |
| 3 — Saved | Cross-session | `business_memories` table | Persistent, owner-editable |

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/memory` | List memories (optional `?category=` filter) |
| POST | `/api/memory` | Create memory manually |
| PATCH | `/api/memory/{id}` | Update a memory |
| DELETE | `/api/memory/{id}` | Delete a memory |
| DELETE | `/api/memory` | Reset all memories |
| GET | `/api/memory/categories` | List distinct categories |

## Signal Tags

| Tag | Direction | Purpose |
|-----|-----------|---------|
| `<memory_save>CATEGORY:KEY:VALUE</memory_save>` | AI -> Backend | Propose saving to memory |
| `<memory_save_confirmed>true</memory_save_confirmed>` | AI -> Backend | Owner confirmed save |

## Categories

hours, preferences, clients, services, pricing, policies, general

## UI

- **Memory page** (`/settings/memory`): View, add, edit, delete memories. Grouped by category.
- **Chat cards**: Purple confirmation card when AI suggests saving, green/red result banner.
- **Sidebar**: "Memory" nav item with Brain icon.

## Prompt Injection

Saved memories are injected at the end of Claude's system prompt in a labeled section:
```
--- MEMORY CONTEXT ---
=== SAVED BUSINESS MEMORY (Tier 3 — persistent, owner-editable) ===
- [hours] Business hours: 9am-5pm EST, Monday through Friday
- [clients] VIP clients: Jane Smith, Mike Johnson
=== SESSION CONTEXT (Tier 2 — this conversation only) ===
- Current task: setting up a workflow
--- END MEMORY CONTEXT ---
```

Capped at 20 memories, values truncated to 200 chars to prevent prompt bloat.

## How to Test

1. **Memory page**: Go to `/settings/memory` — should show empty state
2. **Manual add**: Click "Add Memory" — fill in category, label, value — verify card appears
3. **Edit**: Click pencil icon — modify value — verify update
4. **Delete**: Click trash icon — confirm — verify removal
5. **Chat save flow**: Start a conversation, say "My business hours are 9am-5pm Monday through Friday"
   - Claude should suggest saving — purple card appears
   - Reply "yes" — green "Saved!" banner appears
6. **Memory page confirms**: Navigate to `/settings/memory` — entry should appear with "via chat" badge
7. **Cross-conversation recall**: Start NEW conversation — ask "What are my business hours?" — Claude should know
8. **Reset**: Click "Reset All Memories" — confirm — all entries removed

## Files Changed

### New Files
- `backend/app/models/memory.py` — BusinessMemory model
- `backend/app/schemas/memory.py` — Pydantic schemas
- `backend/app/routers/memory.py` — CRUD API endpoints
- `frontend/src/app/settings/memory/page.tsx` — Memory management page
- `docs/phase-18d-memory.md` — This file

### Modified Files
- `backend/app/models/conversation.py` — Added `session_context` JSON column
- `backend/app/models/__init__.py` — Registered BusinessMemory
- `backend/app/database.py` — Added migration + model import
- `backend/app/main.py` — Mounted memory router
- `backend/app/services/ai_engine.py` — Memory context builder, system prompt, signal tag parsing, get_ai_response params
- `backend/app/routers/chat.py` — Memory query/injection, signal handlers, history builder, session context
- `frontend/src/components/Sidebar.tsx` — Added Memory nav item
- `frontend/src/components/MessageBubble.tsx` — Added memory_save_request/result card types
