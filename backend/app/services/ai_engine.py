import re
from typing import List, Dict, Tuple, Optional
from anthropic import AsyncAnthropic
from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
You are AImplify, a friendly assistant that helps small business owners save time \
by handling their repetitive tasks. You speak in plain, simple language — like a \
smart new employee who's eager to learn how the business works.

IMPORTANT RULES:
- Never say: "trigger," "workflow," "action," "automation," "integration," "API," \
"pipeline," or "agent." Instead say things like "the thing that kicks it off," \
"each step," "the tools you use."
- Ask ONE question at a time. Never dump a list of questions.
- When possible, offer 2-4 simple choices instead of open-ended questions.
- Keep responses short and conversational — 2-3 sentences max per turn.

IMMEDIATE ACTIONS — DO SOMETHING RIGHT NOW:

If the user asks you to do something right now (not set up a recurring process), \
treat it as an immediate action. Recognize requests like:
- "Send Jane a welcome email at jane@example.com" → send_email
- "Create a calendar event for Friday at 2pm" → create_event
- "Check my availability tomorrow morning" → check_availability
- "What's on my calendar this week?" → list_events

When you recognize an immediate action request:
1. FIRST check if you have ALL the details needed to execute. If anything is missing, \
ask ONE follow-up question to fill in the gap. Do NOT include any hidden tags yet. \
For example:
   - Email: you need recipient, subject, and body content. If they just say "send Jane an email," \
ask what the email should say.
   - Calendar event: you need title, date/time, AND duration or end time. If they say \
"create an event for Friday at 2pm," ask "How long should it be — 30 minutes, an hour, \
or something else?"
   - Availability check: you need a time range. If they say "am I free tomorrow," ask \
"What time range should I check — morning, afternoon, or a specific window?"
2. Once you have ALL details, summarize exactly what you'll do and confirm with the user. \
For example: "I'll create a 'Team Standup' event for tomorrow (April 9) from 2:00 PM to \
2:30 PM — sound good?"
3. At the very end of your message (after everything else), append this hidden tag on its own line:
<action_request>ACTION_TYPE</action_request>
Replace ACTION_TYPE with one of: send_email, create_event, check_availability, list_events

When the user confirms the action ("yes," "go ahead," "do it," "sounds good"):
1. Respond with something short like "On it — let me take care of that!"
2. At the very end of your message, append this hidden tag on its own line:
<action_confirmed>true</action_confirmed>

If the user says "no" or wants to change something about the action, ask what to change \
and re-present the details with the <action_request> tag again.

WORKFLOW SETUP — SET UP A RECURRING PROCESS:

If the user describes a task they want to happen automatically or repeatedly (not a \
one-time action), follow the workflow discovery flow below.

1. OPENING — If there is only one user message in the conversation (the first message), \
greet them warmly and ask:
"What's a task that you or your team does over and over that eats up your time?"

2. DISCOVERY — Ask follow-up questions one at a time, in roughly this order:
   a) What is the task? (Let them describe it freely)
   b) What kicks it off? Offer choices like:
      "What usually starts this? Is it:
       • A new appointment or booking
       • An email or message coming in
       • A certain time each day or week
       • Something else?"
   c) How often does it happen? Offer choices:
      "How often does this come up — every day, a few times a week, or just now and then?"
   d) What tools are involved? Offer choices:
      "What tools do you use for this? Things like:
       • Email
       • Text messages
       • Your calendar
       • A spreadsheet or form
       • Something else?"
   e) Walk me through the steps — ask them to describe it start to finish
   f) Are there any special cases? ("Does anything change depending on the situation?")

3. SUMMARY — When you have enough information to describe the full process, present it \
as a numbered list under the heading:
"Here's what I understood about your process:"

Then ask: "Did I get that right? You can say yes, or tell me what I should change."

At the very end of your message (after everything else), append this hidden tag on its \
own line. The user will never see it:
<workflow_ready>true</workflow_ready>

4. CONFIRMATION — When the user confirms with "yes," "that's right," "looks good," \
or similar:
- Respond with a short, warm confirmation like "Great, I've saved that!"
- At the very end of your message, append this hidden tag on its own line:
<workflow_confirmed>true</workflow_confirmed>

5. CORRECTIONS — If the user says "no" or wants to change something:
- Ask what to change, update your understanding, and re-present the summary
- Include the <workflow_ready>true</workflow_ready> tag again at the end

6. MULTIPLE TASKS — If the user describes more than one task, pick the first one:
"It sounds like you have a few things going on! Let's start with [X] — we can \
tackle the others right after."

7. OFF-TOPIC — If the user goes off-topic, gently steer back:
"That's helpful context! To keep things moving — were there any other steps in \
that process?"
"""

# Tool definition for structured workflow extraction
WORKFLOW_TOOL = {
    "name": "save_workflow",
    "description": "Save a structured workflow extracted from the conversation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Short, plain-English name for this workflow (e.g., 'New client welcome')",
            },
            "description": {
                "type": "string",
                "description": "One-sentence description of what this workflow does",
            },
            "trigger_type": {
                "type": "string",
                "enum": ["schedule", "event", "manual"],
                "description": "What kicks off this workflow",
            },
            "trigger_config": {
                "type": "object",
                "properties": {
                    "frequency": {
                        "type": "string",
                        "description": "How often (e.g., 'daily', 'weekly', 'on_event')",
                    },
                    "event_type": {
                        "type": "string",
                        "description": "Specific event (e.g., 'new_booking', 'email_received')",
                    },
                    "schedule": {
                        "type": "string",
                        "description": "Schedule description if time-based (e.g., 'every morning at 9am')",
                    },
                },
                "required": ["frequency"],
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step_order": {"type": "integer"},
                        "action_type": {
                            "type": "string",
                            "description": "Action type (e.g., 'send_email', 'send_sms', 'check_calendar')",
                        },
                        "description": {
                            "type": "string",
                            "description": "Plain-English description of this step",
                        },
                        "action_config": {
                            "type": "object",
                            "description": "Step-specific configuration details",
                        },
                    },
                    "required": ["step_order", "action_type", "description"],
                },
            },
        },
        "required": ["name", "description", "trigger_type", "trigger_config", "steps"],
    },
}

EXTRACTION_PROMPT = """\
You are a workflow extraction system. Analyze the conversation below and extract \
the structured workflow the user described. Identify the trigger (what kicks it off), \
the steps (in order), and any conditions or tools mentioned. Use the save_workflow \
tool to output the result. Be precise and complete — capture every step the user described.\
"""


def parse_ai_response(raw_content: str) -> dict:
    """Strip hidden signal tags from AI response and return flags.

    Returns dict with keys: clean_content, workflow_ready, workflow_confirmed,
    action_request (str or None), action_confirmed.
    """
    workflow_ready = "<workflow_ready>true</workflow_ready>" in raw_content
    workflow_confirmed = "<workflow_confirmed>true</workflow_confirmed>" in raw_content
    action_confirmed = "<action_confirmed>true</action_confirmed>" in raw_content

    # Extract action_request type (e.g., "send_email" from <action_request>send_email</action_request>)
    action_request = None
    action_match = re.search(r"<action_request>(\w+)</action_request>", raw_content)
    if action_match:
        action_request = action_match.group(1)

    clean = raw_content
    clean = clean.replace("<workflow_ready>true</workflow_ready>", "")
    clean = clean.replace("<workflow_confirmed>true</workflow_confirmed>", "")
    clean = clean.replace("<action_confirmed>true</action_confirmed>", "")
    if action_match:
        clean = clean.replace(action_match.group(0), "")
    clean = clean.strip()

    return {
        "clean_content": clean,
        "workflow_ready": workflow_ready,
        "workflow_confirmed": workflow_confirmed,
        "action_request": action_request,
        "action_confirmed": action_confirmed,
    }


# ── Action extraction tools ─────────────────────────────────────────────────

ACTION_EXTRACTION_TOOLS = {
    "send_email": {
        "name": "prepare_email",
        "description": "Extract email parameters from the conversation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body, friendly and professional"},
            },
            "required": ["recipient", "subject", "body"],
        },
    },
    "create_event": {
        "name": "prepare_event",
        "description": "Extract calendar event parameters from the conversation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title"},
                "start_time": {"type": "string", "description": "ISO 8601 start time with timezone offset (e.g. 2026-04-09T14:00:00-05:00)"},
                "end_time": {"type": "string", "description": "ISO 8601 end time with timezone offset (e.g. 2026-04-09T14:42:00-05:00)"},
                "description": {"type": "string", "description": "Event notes (optional)"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Email addresses of people to invite (optional)",
                },
            },
            "required": ["summary", "start_time", "end_time"],
        },
    },
    "check_availability": {
        "name": "prepare_availability_check",
        "description": "Extract time range for availability check from the conversation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_time": {"type": "string", "description": "ISO 8601 start time"},
                "end_time": {"type": "string", "description": "ISO 8601 end time"},
            },
            "required": ["start_time", "end_time"],
        },
    },
}

ACTION_EXTRACTION_PROMPT = """\
You are a parameter extraction system. Analyze the conversation and extract the \
exact parameters needed to execute the requested action. Use the provided tool to \
output the result. Be precise — use the details the user provided.

IMPORTANT: For dates and times, convert relative references (like "tomorrow", \
"next Friday", "this afternoon") into full ISO 8601 timestamps using today's date \
as reference. Today is {today}. The user's timezone is {timezone}. Always use this \
timezone for the timestamps (e.g., if timezone is America/Chicago, use offset -05:00 \
or -06:00 depending on DST). If a duration is given instead of an end time, calculate \
the end time from the start time plus the duration.\
"""


async def extract_action_from_conversation(
    messages: List[Dict[str, str]], action_type: str, timezone: str = "UTC"
) -> Optional[dict]:
    """Extract structured action parameters from the conversation using tool_use."""
    from datetime import datetime, timezone as tz

    tool = ACTION_EXTRACTION_TOOLS.get(action_type)
    if not tool:
        return None

    today = datetime.now(tz.utc).strftime("%A, %B %d, %Y (%Y-%m-%d)")
    system_prompt = ACTION_EXTRACTION_PROMPT.format(today=today, timezone=timezone)

    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == tool["name"]:
                return block.input

        return None
    except Exception:
        return None


async def get_ai_response(messages: List[Dict[str, str]], timezone: str = "UTC") -> str:
    """Send messages to Claude and return the assistant's response."""
    from datetime import datetime, timezone as tz

    today = datetime.now(tz.utc).strftime("%A, %B %d, %Y")
    system = SYSTEM_PROMPT + f"\n\nToday's date is {today}. The user's timezone is {timezone}."

    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return response.content[0].text


async def extract_workflow_from_conversation(messages: List[Dict[str, str]]) -> Optional[dict]:
    """Make a second Claude call to extract structured workflow JSON from the conversation.

    Uses tool_use with forced tool_choice to guarantee valid structured output.
    """
    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=EXTRACTION_PROMPT,
            messages=messages,
            tools=[WORKFLOW_TOOL],
            tool_choice={"type": "tool", "name": "save_workflow"},
        )

        # Extract the tool use input from the response
        for block in response.content:
            if block.type == "tool_use" and block.name == "save_workflow":
                return block.input

        return None
    except Exception:
        # Graceful degradation — if extraction fails, conversation continues normally
        return None
