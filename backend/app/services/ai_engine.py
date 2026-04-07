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

CONVERSATION FLOW:

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


def parse_ai_response(raw_content: str) -> Tuple[str, bool, bool]:
    """Strip hidden signal tags from AI response and return flags.

    Returns (clean_content, workflow_ready, workflow_confirmed).
    """
    workflow_ready = "<workflow_ready>true</workflow_ready>" in raw_content
    workflow_confirmed = "<workflow_confirmed>true</workflow_confirmed>" in raw_content

    clean = raw_content.replace("<workflow_ready>true</workflow_ready>", "")
    clean = clean.replace("<workflow_confirmed>true</workflow_confirmed>", "")
    clean = clean.strip()

    return clean, workflow_ready, workflow_confirmed


async def get_ai_response(messages: List[Dict[str, str]]) -> str:
    """Send messages to Claude and return the assistant's response."""
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
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
