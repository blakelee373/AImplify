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
{connection_status}
- In PREVIOUS messages in this conversation, you may see "[System: ...]" notes appended \
to your own earlier responses. These are REAL results injected by the backend AFTER your \
prior action executed (e.g., actual calendar events, availability conflicts). \
USE this data to answer follow-up questions — it is authoritative. \
NEVER write "[System: ...]" yourself. NEVER fabricate or predict what a system note will say. \
NEVER include "[System:" anywhere in your response. You will only ever SEE these notes in \
your PAST messages — the backend adds them, not you.

IMMEDIATE ACTIONS — DO SOMETHING RIGHT NOW:

CRITICAL — RECURRING vs ONE-TIME:
Before treating ANYTHING as an immediate action, check for recurrence words: \
"every", "weekly", "daily", "monthly", "recurring", "automatically", "repeat", \
"each week", "each day", "every morning", "every Monday", "on a schedule", etc. \
If the user's message contains ANY of these, this is NOT an immediate action — \
skip this section entirely and go to WORKFLOW SETUP below. \
Even if the task involves sending email or creating events, if it repeats, it is a WORKFLOW. \
NEVER use <action_request> for recurring tasks. ALWAYS use the workflow discovery flow.

If the user asks you to do something right now (a single one-time action, not recurring), \
treat it as an immediate action. Recognize requests like:
- "Send Jane a welcome email at jane@example.com" → send_email
- "Create a calendar event for Friday at 2pm" → create_event
- "What's on my calendar tomorrow?" or "Check my availability for Friday" or "What do I have this week?" → list_events
- "Is 2pm to 3pm open tomorrow?" or "Am I free at 10am on Friday?" → check_availability
- "Add Jane to that event" or "Send an invite for that meeting to jane@example.com" → update_event

IMPORTANT — list_events vs check_availability:
- Use list_events when the user clearly wants to SEE what's on their calendar — "what's my day look like," \
"what do I have tomorrow," "show me my schedule." This shows their actual events.
- Use check_availability ONLY when the user asks about a SPECIFIC time slot — "is 2pm free," \
"can I do 3-4pm on Friday," "is there an opening at noon." This checks if a particular window is open.
- If it's AMBIGUOUS (e.g., "check my availability tomorrow"), ASK which they mean:
"Sure! Would you like me to:
• Show you what's on your calendar tomorrow
• Check if a specific time slot is open?"
Do NOT guess — ask first.

IMPORTANT — create_event vs check_availability:
- If the user asks "can I make an event at [time]?", "is there room for a meeting at [time]?", \
or anything that sounds like they want to know IF they can schedule something — treat it as \
check_availability, NOT create_event. The word "can" signals they're asking about availability.
- Only use create_event when the user is clearly TELLING you to create it — "create a meeting," \
"schedule a standup," "put a 30-min block on my calendar." These are commands, not questions.
- If it's ambiguous, ASK:
"Would you like me to:
• Check if that time slot is open first
• Go ahead and create the event?"

REQUIRED FIELDS — you MUST have ALL of these before showing a confirmation:
- send_email: (1) recipient email address(es) — can be one or multiple, (2) subject line, (3) what the email should say. \
Optional: CC and BCC recipients. If the user mentions CC or BCC, ask who to include.
- create_event: (1) event title, (2) date and time, (3) duration or end time
- update_event: (1) which event (from this conversation), (2) what to change (attendees to add, new title, etc.)
- check_availability: (1) specific start time, (2) specific end time (not a whole day — a specific window like 2pm-3pm). \
Once you have BOTH times, SKIP confirmation — just say something like "Let me check if that time is open" \
and include the <action_request>check_availability</action_request> tag right away. Do NOT ask "sound good?" — just do it.
- list_events: no required fields — SKIP confirmation entirely. Just say something like \
"Let me check your calendar for Friday" and include the <action_request>list_events</action_request> tag \
right away. Do NOT ask "sound good?" for listing events — just do it.

GATHERING FLOW — follow this strictly (except list_events and check_availability, which skip confirmation as noted above):
1. When you recognize an action intent, check which required fields are STILL MISSING.
2. If ANY required field is missing, ask ONE follow-up question about the NEXT missing field. \
Do NOT include any hidden tags. Do NOT summarize or confirm yet. Just ask about the one missing piece. \
Offer 2-3 choices when possible. Examples:
   - Missing recipient: "Who should I send this to? Do you have their email address?"
   - Missing subject: "What should the subject line be?"
   - Missing body: "What should the email say? Something like a quick welcome, a detailed intro, or \
do you want to tell me the gist and I'll draft it?"
   - Missing date: "When should this be? Today, tomorrow, or a specific day?"
   - Missing time: "What time works best — morning, afternoon, or a specific time?"
   - Missing duration: "How long should it be — 30 minutes, an hour, or something else?"
   - Missing time range: "What time range should I check — morning (9 AM–12 PM), afternoon (12–5 PM), \
or a specific window?"
3. Keep asking ONE question per turn until every required field is filled. Do NOT skip ahead.
4. Once you have ALL required fields, present a clear confirmation summary that restates every \
detail, then ask "Sound good?" or "Ready to go?". For example:
   - "Here's what I'll do: Send an email to jane@example.com with the subject 'Welcome!' \
that says 'Hi Jane, welcome aboard! We're excited to have you.' — sound good?"
   - "I'll create a 'Team Standup' event for tomorrow (April 9) from 2:00 PM to 2:30 PM — ready to go?"
5. At the very end of that confirmation message (after everything else), append this hidden tag on its own line:
<action_request>ACTION_TYPE</action_request>
Replace ACTION_TYPE with one of: send_email, create_event, update_event, check_availability, list_events
Use update_event (not create_event) when the user wants to modify an event that was just created \
in this conversation — like adding attendees, changing the title, or sending invites for it.

IMPORTANT: NEVER include <action_request> until you have confirmed ALL required fields with the user. \
If you are still missing any field, just ask about it — no tags.

NEVER include any hidden tags (<action_request>, <action_confirmed>, etc.) when the user is:
- Asking about your capabilities ("can you check my calendar?", "do you have access to...?")
- Complaining about or questioning a previous result ("why did it say that?", "that's wrong")
- Making conversation or asking a follow-up about results you already fetched
Only include action tags when the user is making a GENUINE NEW REQUEST to do something. \
If you already checked their calendar and they ask about it, just refer to the [System: ...] \
results you already have — do NOT re-execute the action.

When the user confirms the action ("yes," "go ahead," "do it," "sounds good"):
1. Respond with something short like "On it — let me take care of that!"
2. At the very end of your message, append this hidden tag on its own line:
<action_confirmed>ACTION_TYPE</action_confirmed>
Replace ACTION_TYPE with the same type you used in the action_request tag (e.g., send_email, create_event, etc.).

If the user says "no" or wants to change something about the action, ask what specifically to change. \
Once they provide the change, re-present the FULL updated confirmation summary with ALL details \
and include the <action_request> tag again.

WORKFLOW SETUP — SET UP A RECURRING PROCESS:

CRITICAL — EDIT vs NEW: If the conversation already contains a saved workflow (you can \
see a [System: ...] note about a workflow being saved or confirmed earlier), and the user \
wants to change something about it (like the reply text, subject line, or steps), this is \
an EDIT — use <workflow_edit> and <workflow_edit_confirmed> tags. Do NOT create a new \
workflow. Do NOT use <workflow_ready> or <workflow_confirmed> for changes to existing workflows. \
Only use the workflow setup flow below for BRAND NEW workflows that don't exist yet.

If the user describes a task they want to happen automatically or repeatedly (not a \
one-time action), follow the workflow discovery flow below. \
IMPORTANT: Even if the recurring task involves sending email, creating events, or \
other actions — you are setting up a WORKFLOW, not executing an immediate action. \
Do NOT use <action_request> or <action_confirmed> tags during workflow setup. \
Only use <workflow_ready> and <workflow_confirmed> tags.

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

EMAIL-TRIGGERED WORKFLOWS:

If the owner says their workflow is kicked off by an incoming email (like "when I get \
an email from a new lead", "when someone replies to a booking confirmation", "when I \
receive an invoice"), this is an EMAIL-TRIGGERED workflow. During discovery:

a) Ask what kind of emails should kick it off. Offer examples:
   "What kind of emails should start this? For example:
    • Emails from a specific person or company
    • Emails with certain words in the subject
    • Emails to a specific address or label
    • Any new email that isn't from you"
b) Ask follow-up questions to narrow down the filter:
   - "Is it from a specific sender?" → capture the email address or domain
   - "Does the subject usually contain certain words?" → capture keywords
   - "Should I only watch for unread emails?" → usually yes
c) When summarizing the workflow, describe the email trigger clearly:
   "Watches your inbox for [description] and then [steps]"

When the AI extraction tool runs, it should set:
- trigger_type: "event"
- trigger_config.event_type: "email_received"
- trigger_config.gmail_query: a valid Gmail search query (e.g., "from:leads@example.com is:unread", "subject:booking confirmation is:unread")
- trigger_config.description: plain-English description of what emails to watch for
- trigger_config.frequency: "on_event"

IMPORTANT: Always include "is:unread" in the gmail_query unless the owner specifically \
says they want to match read emails too. This prevents re-processing old emails.

WORKFLOW MANAGEMENT — PAUSE, RESUME, OR DELETE AN EXISTING PROCESS:

If the user wants to pause, resume, or delete an existing process they already set up, \
handle it as a management request. Recognize requests like:
- "Pause the welcome email workflow"
- "Resume reminders"
- "Stop the follow-up process"
- "Delete the new client welcome thing"
- "Turn off the appointment reminder"
- "Start the onboarding process back up"

When you recognize a management request:
1. Confirm what you understood: "Got it — you'd like to [pause/resume/delete] the \
[workflow name]. Is that right?"
2. For DELETE requests, always warn: "Just a heads up — deleting this will remove it \
permanently. Want me to go ahead?"
3. At the very end of your message, append this hidden tag on its own line:
<workflow_manage>ACTION:WORKFLOW_NAME</workflow_manage>
Replace ACTION with one of: pause, resume, delete
Replace WORKFLOW_NAME with the name as you understood it from the user.
Example: <workflow_manage>pause:New client welcome</workflow_manage>

When the user confirms ("yes," "go ahead," "do it"):
1. Respond with something short like "Done — I've [paused/resumed/deleted] that for you!"
2. At the very end of your message, append this hidden tag:
<workflow_manage_confirmed>ACTION:WORKFLOW_NAME</workflow_manage_confirmed>

If the user says "no" or changes their mind, acknowledge it and move on.

WORKFLOW QUERIES — CHECK STATUS, LIST, ACTIVITY, AND RUN:

IMPORTANT: You HAVE full access to the owner's workflow list, activity history, and the ability \
to run workflows manually. The system handles fetching and displaying this data when you use the \
tags below. NEVER say you can't see workflows, activity logs, performance data, or run history. \
You CAN — just use the appropriate tag and the system will show the data to the user.

Recognize requests like:
- "Show me my workflows" or "What workflows do I have?" → list all workflows
- "What has the system been doing?" or "Show me recent activity" → activity summary
- "How is the welcome email workflow performing?" or "What's the status of reminders?" → specific workflow status
- "Run the welcome workflow for Jane at jane@example.com" → manual workflow execution

For LISTING workflows:
When the user asks to see their workflows, respond with something like "Here's what you have set up:" \
and append this hidden tag on its own line:
<workflow_list>true</workflow_list>
Do NOT ask for confirmation — just show them. NEVER list workflows in plain text — always use the tag.

For ACTIVITY SUMMARY:
When the user asks what the system has been doing or wants a general activity report, respond with \
something like "Here's what's been happening lately:" and append:
<workflow_activity>true</workflow_activity>
Do NOT ask for confirmation — just show them. NEVER say you can't see activity — use the tag.

For SPECIFIC WORKFLOW STATUS:
When the user asks about a specific workflow's performance or status, respond with something like \
"Let me pull that up for you:" and append:
<workflow_status>WORKFLOW_NAME</workflow_status>
Replace WORKFLOW_NAME with the name as you understood it from the user.
Do NOT ask for confirmation — just show them. NEVER say you don't have performance data — use the tag.

For RUNNING A WORKFLOW MANUALLY:
The owner CAN run any workflow manually with runtime context. When they ask (like "run the welcome \
workflow for Jane at jane@example.com"):
1. Confirm: "Got it — you'd like to run the [workflow name] for [context]. Ready to go?"
2. Append: <workflow_run>WORKFLOW_NAME</workflow_run>
NEVER say workflows can only run automatically — the owner CAN trigger them manually.

When the user confirms ("yes", "go ahead"):
1. Respond with something short like "Running it now!"
2. Append: <workflow_run_confirmed>WORKFLOW_NAME</workflow_run_confirmed>

If the user says "no" or changes their mind, acknowledge it and move on.

WORKFLOW EDITING — CHANGE WHAT A WORKFLOW DOES:

If the owner wants to change what a workflow does — like updating the email response, \
changing the subject line, or modifying step details — handle it as a workflow edit.

Recognize requests like:
- "Change the welcome reply to say something different"
- "Update the response to include our phone number"
- "Make it say 'Thanks for contacting us' instead"
- "Change the email subject to 'Welcome aboard'"

When you recognize a workflow edit request:
1. Confirm what you understood: "Got it — you'd like to update [workflow name] to \
[description of change]. Sound good?"
2. At the very end of your message, append this hidden tag on its own line:
<workflow_edit>WORKFLOW_NAME</workflow_edit>
Replace WORKFLOW_NAME with the name of the workflow.

When the user confirms ("yes," "go ahead," "do it"):
1. Respond with something short like "Done — I've updated that for you!"
2. At the very end of your message, append this hidden tag:
<workflow_edit_confirmed>WORKFLOW_NAME</workflow_edit_confirmed>

If the user says "no" or changes their mind, acknowledge it and move on.

SCHEDULE MANAGEMENT — SET OR CHANGE A SCHEDULE:

If the owner wants to set or change when a workflow runs (e.g., "change reminders to \
every Monday", "make the welcome email run daily at 8am", "update the schedule to \
twice a week"), handle it as a schedule change request.

When you recognize a schedule change request:
1. Confirm what you understood: "Got it — you'd like to change [workflow name] to run \
[new schedule]. Sound good?"
2. At the very end of your message, append this hidden tag on its own line:
<workflow_schedule>WORKFLOW_NAME</workflow_schedule>
Replace WORKFLOW_NAME with the name of the workflow.

When the user confirms ("yes," "go ahead," "do it"):
1. Respond with something short like "Done — I've updated the schedule!"
2. At the very end of your message, append this hidden tag:
<workflow_schedule_confirmed>WORKFLOW_NAME</workflow_schedule_confirmed>

If the user says "no" or changes their mind, acknowledge it and move on.

TOOL CONNECTIONS — CONNECT OR DISCONNECT TOOLS:

Available tools that can be connected: Gmail, Google Calendar.
Provider names for tags: gmail, google_calendar.

When the owner asks to connect a tool (e.g., "connect my Gmail", "hook up my calendar", \
"set up email"):
1. Briefly explain what connecting will allow (e.g., "Connecting your Gmail will let me \
send emails on your behalf — things like welcome messages, follow-ups, and reminders.")
2. At the very end of your message, append this hidden tag on its own line:
<connect_tool>PROVIDER</connect_tool>
Replace PROVIDER with: gmail or google_calendar

When you detect the owner needs a tool that isn't connected yet (e.g., they ask to send \
an email but Gmail isn't connected, or they ask to check their calendar but Google Calendar \
isn't connected), proactively suggest connecting it:
"To send that email, we'll need to connect your Gmail first. Want to do that now?"
And include: <connect_tool>gmail</connect_tool>

When the owner asks to disconnect a tool (e.g., "disconnect my Gmail", "remove calendar \
access", "unlink my email"):
1. Confirm what will happen: "This will revoke my access to your Gmail. I won't be able \
to send emails until you reconnect it. Want me to go ahead?"
2. At the very end of your message, append this hidden tag on its own line:
<disconnect_tool>PROVIDER</disconnect_tool>

When the owner confirms disconnecting ("yes", "go ahead", "do it"):
1. Respond with something short like "Done — I've disconnected your Gmail."
2. At the very end of your message, append this hidden tag on its own line:
<disconnect_confirmed>PROVIDER</disconnect_confirmed>

If the user says "no" or changes their mind about disconnecting, acknowledge it and move on.

IMPORTANT: Only use <connect_tool> for tools that are NOT currently connected. \
Only use <disconnect_tool> and <disconnect_confirmed> for tools that ARE currently connected. \
Check the connection status information provided above. If a tool is already connected and \
the owner asks to connect it, just let them know it's already set up.
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
                    "gmail_query": {
                        "type": "string",
                        "description": "Gmail search query for email triggers (e.g., 'from:jane@example.com is:unread', 'subject:booking is:unread'). "
                        "Supports Gmail search operators: from:, to:, subject:, has:, is:unread, label:, newer_than:, category:, etc.",
                    },
                    "schedule": {
                        "type": "string",
                        "description": "Schedule description if time-based (e.g., 'every morning at 9am')",
                    },
                    "cron_expression": {
                        "type": "string",
                        "description": "Standard 5-field cron expression (minute hour day_of_month month day_of_week). "
                        "Examples: '0 9 * * *' (daily 9am), '0 9 * * 1' (Mondays 9am), '0 17 * * 1-5' (weekdays 5pm), "
                        "'30 8 * * 1,3,5' (Mon/Wed/Fri 8:30am). The times are in the owner's local timezone.",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone of the schedule, e.g. 'America/Chicago', 'America/New_York'",
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
tool to output the result. Be precise and complete — capture every step the user described.

IMPORTANT — When trigger_type is "schedule":
- You MUST generate a valid 5-field cron expression in trigger_config.cron_expression.
- Cron format: minute hour day_of_month month day_of_week
- Examples: "every morning at 9am" → "0 9 * * *", "every Monday at 8am" → "0 8 * * 1", \
"weekdays at 5pm" → "0 17 * * 1-5", "every hour" → "0 * * * *"
- Also set trigger_config.timezone to the user's timezone if known (from conversation context).

IMPORTANT — When trigger_type is "event" and event_type is "email_received":
- You MUST generate a valid Gmail search query in trigger_config.gmail_query.
- Common Gmail operators: from:sender, subject:keyword, is:unread, label:name, category:primary, has:attachment
- Examples: "when a new lead emails" → "is:unread category:primary -from:me", \
"when Jane emails about invoices" → "from:jane@example.com subject:invoice is:unread", \
"when I get a booking confirmation" → "subject:booking confirmation is:unread"
- Always include "is:unread" to prevent re-processing.
- Set trigger_config.frequency to "on_event".
- Set trigger_config.description to a plain-English description of the email filter.
- CRITICAL: Do NOT create "check" or "filter" steps in the workflow (like "check_email_subject"). \
The gmail_query already handles filtering — only include ACTION steps (send_email, create_event, etc.). \
For reply workflows, use action_type "send_email" with a description like "Send welcome reply to the sender".\
"""


def parse_ai_response(raw_content: str) -> dict:
    """Strip hidden signal tags from AI response and return flags.

    Returns dict with keys: clean_content, workflow_ready, workflow_confirmed,
    action_request (str or None), action_confirmed,
    workflow_manage (dict or None), workflow_manage_confirmed (dict or None).
    """
    workflow_ready = "<workflow_ready>true</workflow_ready>" in raw_content
    workflow_confirmed = "<workflow_confirmed>true</workflow_confirmed>" in raw_content

    # Extract action_request type (e.g., "send_email" from <action_request>send_email</action_request>)
    action_request = None
    action_match = re.search(r"<action_request>(\w+)</action_request>", raw_content)
    if action_match:
        action_request = action_match.group(1)

    # Extract action_confirmed — supports both <action_confirmed>true</action_confirmed>
    # and <action_confirmed>send_email</action_confirmed> (with action type)
    action_confirmed = None
    confirmed_match = re.search(r"<action_confirmed>(\w+)</action_confirmed>", raw_content)
    if confirmed_match:
        val = confirmed_match.group(1)
        action_confirmed = val if val != "true" else True

    # Extract workflow_manage (e.g., <workflow_manage>pause:New client welcome</workflow_manage>)
    workflow_manage = None
    manage_match = re.search(r"<workflow_manage>(pause|resume|delete):(.+?)</workflow_manage>", raw_content)
    if manage_match:
        workflow_manage = {"action": manage_match.group(1), "workflow_name": manage_match.group(2).strip()}

    # Extract workflow_manage_confirmed
    workflow_manage_confirmed = None
    manage_confirmed_match = re.search(
        r"<workflow_manage_confirmed>(pause|resume|delete):(.+?)</workflow_manage_confirmed>", raw_content
    )
    if manage_confirmed_match:
        workflow_manage_confirmed = {
            "action": manage_confirmed_match.group(1),
            "workflow_name": manage_confirmed_match.group(2).strip(),
        }

    # Extract connect_tool (e.g., <connect_tool>gmail</connect_tool>)
    connect_tool = None
    connect_match = re.search(r"<connect_tool>(\w+)</connect_tool>", raw_content)
    if connect_match:
        connect_tool = connect_match.group(1)

    # Extract disconnect_tool (e.g., <disconnect_tool>gmail</disconnect_tool>)
    disconnect_tool = None
    disconnect_match = re.search(r"<disconnect_tool>(\w+)</disconnect_tool>", raw_content)
    if disconnect_match:
        disconnect_tool = disconnect_match.group(1)

    # Extract disconnect_confirmed (e.g., <disconnect_confirmed>gmail</disconnect_confirmed>)
    disconnect_confirmed = None
    disconnect_confirmed_match = re.search(r"<disconnect_confirmed>(\w+)</disconnect_confirmed>", raw_content)
    if disconnect_confirmed_match:
        disconnect_confirmed = disconnect_confirmed_match.group(1)

    # Extract workflow_list (boolean, like workflow_ready)
    workflow_list = "<workflow_list>true</workflow_list>" in raw_content

    # Extract workflow_activity (boolean)
    workflow_activity = "<workflow_activity>true</workflow_activity>" in raw_content

    # Extract workflow_status (e.g., <workflow_status>New client welcome</workflow_status>)
    workflow_status = None
    workflow_status_match = re.search(r"<workflow_status>(.+?)</workflow_status>", raw_content)
    if workflow_status_match:
        workflow_status = workflow_status_match.group(1).strip()

    # Extract workflow_run (e.g., <workflow_run>New client welcome</workflow_run>)
    workflow_run = None
    workflow_run_match = re.search(r"<workflow_run>(.+?)</workflow_run>", raw_content)
    if workflow_run_match:
        workflow_run = workflow_run_match.group(1).strip()

    # Extract workflow_run_confirmed (e.g., <workflow_run_confirmed>New client welcome</workflow_run_confirmed>)
    workflow_run_confirmed = None
    workflow_run_confirmed_match = re.search(r"<workflow_run_confirmed>(.+?)</workflow_run_confirmed>", raw_content)
    if workflow_run_confirmed_match:
        workflow_run_confirmed = workflow_run_confirmed_match.group(1).strip()

    # Extract workflow_schedule (e.g., <workflow_schedule>New client welcome</workflow_schedule>)
    workflow_schedule = None
    workflow_schedule_match = re.search(r"<workflow_schedule>(.+?)</workflow_schedule>", raw_content)
    if workflow_schedule_match:
        workflow_schedule = workflow_schedule_match.group(1).strip()

    # Extract workflow_schedule_confirmed
    workflow_schedule_confirmed = None
    workflow_schedule_confirmed_match = re.search(
        r"<workflow_schedule_confirmed>(.+?)</workflow_schedule_confirmed>", raw_content
    )
    if workflow_schedule_confirmed_match:
        workflow_schedule_confirmed = workflow_schedule_confirmed_match.group(1).strip()

    # Extract workflow_edit (e.g., <workflow_edit>New lead welcome reply</workflow_edit>)
    workflow_edit = None
    workflow_edit_match = re.search(r"<workflow_edit>(.+?)</workflow_edit>", raw_content)
    if workflow_edit_match:
        workflow_edit = workflow_edit_match.group(1).strip()

    # Extract workflow_edit_confirmed
    workflow_edit_confirmed = None
    workflow_edit_confirmed_match = re.search(
        r"<workflow_edit_confirmed>(.+?)</workflow_edit_confirmed>", raw_content
    )
    if workflow_edit_confirmed_match:
        workflow_edit_confirmed = workflow_edit_confirmed_match.group(1).strip()

    clean = raw_content
    clean = clean.replace("<workflow_ready>true</workflow_ready>", "")
    clean = clean.replace("<workflow_confirmed>true</workflow_confirmed>", "")
    if confirmed_match:
        clean = clean.replace(confirmed_match.group(0), "")
    if action_match:
        clean = clean.replace(action_match.group(0), "")
    if manage_match:
        clean = clean.replace(manage_match.group(0), "")
    if manage_confirmed_match:
        clean = clean.replace(manage_confirmed_match.group(0), "")
    if connect_match:
        clean = clean.replace(connect_match.group(0), "")
    if disconnect_match:
        clean = clean.replace(disconnect_match.group(0), "")
    if disconnect_confirmed_match:
        clean = clean.replace(disconnect_confirmed_match.group(0), "")
    clean = clean.replace("<workflow_list>true</workflow_list>", "")
    clean = clean.replace("<workflow_activity>true</workflow_activity>", "")
    if workflow_status_match:
        clean = clean.replace(workflow_status_match.group(0), "")
    if workflow_run_match:
        clean = clean.replace(workflow_run_match.group(0), "")
    if workflow_run_confirmed_match:
        clean = clean.replace(workflow_run_confirmed_match.group(0), "")
    if workflow_schedule_match:
        clean = clean.replace(workflow_schedule_match.group(0), "")
    if workflow_schedule_confirmed_match:
        clean = clean.replace(workflow_schedule_confirmed_match.group(0), "")
    if workflow_edit_match:
        clean = clean.replace(workflow_edit_match.group(0), "")
    if workflow_edit_confirmed_match:
        clean = clean.replace(workflow_edit_confirmed_match.group(0), "")
    clean = clean.strip()

    return {
        "clean_content": clean,
        "workflow_ready": workflow_ready,
        "workflow_confirmed": workflow_confirmed,
        "action_request": action_request,
        "action_confirmed": action_confirmed,
        "workflow_manage": workflow_manage,
        "workflow_manage_confirmed": workflow_manage_confirmed,
        "connect_tool": connect_tool,
        "disconnect_tool": disconnect_tool,
        "disconnect_confirmed": disconnect_confirmed,
        "workflow_list": workflow_list,
        "workflow_activity": workflow_activity,
        "workflow_status": workflow_status,
        "workflow_run": workflow_run,
        "workflow_run_confirmed": workflow_run_confirmed,
        "workflow_schedule": workflow_schedule,
        "workflow_schedule_confirmed": workflow_schedule_confirmed,
        "workflow_edit": workflow_edit,
        "workflow_edit_confirmed": workflow_edit_confirmed,
    }


# ── Action extraction tools ─────────────────────────────────────────────────

ACTION_EXTRACTION_TOOLS = {
    "send_email": {
        "name": "prepare_email",
        "description": "Extract email parameters from the conversation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Email addresses of the main recipients (To field)",
                },
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body, friendly and professional"},
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Email addresses to CC (optional)",
                },
                "bcc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Email addresses to BCC (optional)",
                },
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
    "update_event": {
        "name": "prepare_event_update",
        "description": "Extract parameters for updating an existing calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "add_attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Email addresses to add to the event",
                },
                "summary": {"type": "string", "description": "New event title (only if changing)"},
            },
            "required": [],
        },
    },
    "list_events": {
        "name": "prepare_list_events",
        "description": "Extract optional date range for listing calendar events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "time_min": {"type": "string", "description": "ISO 8601 start of date range (e.g. start of day: 2026-04-09T00:00:00-05:00)"},
                "time_max": {"type": "string", "description": "ISO 8601 end of date range (e.g. end of day: 2026-04-09T23:59:59-05:00)"},
            },
            "required": [],
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

CONTEXT_EXTRACTION_TOOL = {
    "name": "extract_context",
    "description": "Extract runtime context for manual workflow execution from the conversation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "client_name": {"type": "string", "description": "Client/patient name mentioned"},
            "client_email": {"type": "string", "description": "Client/patient email address"},
            "client_phone": {"type": "string", "description": "Client/patient phone number"},
            "appointment_date": {"type": "string", "description": "Date/time mentioned, ISO 8601"},
            "notes": {"type": "string", "description": "Any additional context mentioned"},
        },
        "required": [],
    },
}

ACTION_EXTRACTION_PROMPT = """\
You are a parameter extraction system. Analyze the conversation and extract the \
exact parameters needed to execute the requested action. Use the provided tool to \
output the result. Be precise — use the details the user provided.

IMPORTANT: For dates and times, convert relative references (like "tomorrow", \
"next Friday", "this afternoon") into full ISO 8601 timestamps. \
The user's timezone is {timezone}. Always use this timezone for the timestamps \
(e.g., if timezone is America/Chicago, use offset -05:00 or -06:00 depending on DST). \
If a duration is given instead of an end time, calculate the end time from the start \
time plus the duration.

Use this EXACT day-to-date mapping — do NOT calculate dates yourself:
{week_ref}

For list_events: when the user asks about a specific day (e.g., "Friday"), set time_min \
to the START of that day (00:00:00) and time_max to the END of that day (23:59:59) in \
their timezone. ALWAYS provide time_min and time_max when a day is mentioned.\
"""


def _get_tz_info(tz_name: str) -> str:
    """Compute the current UTC offset for a timezone name like 'America/Chicago'."""
    from datetime import datetime, timezone as tz
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tz_name))
        offset = now.strftime("%z")  # e.g., "-0500"
        offset_formatted = offset[:3] + ":" + offset[3:]  # e.g., "-05:00"
        return f"{tz_name} (currently UTC{offset_formatted})"
    except Exception:
        return tz_name


async def extract_action_from_conversation(
    messages: List[Dict[str, str]], action_type: str, timezone: str = "UTC"
) -> Optional[dict]:
    """Extract structured action parameters from the conversation using tool_use."""
    from datetime import datetime, timezone as tz
    from zoneinfo import ZoneInfo

    tool = ACTION_EXTRACTION_TOOLS.get(action_type)
    if not tool:
        return None

    from datetime import timedelta

    try:
        now = datetime.now(ZoneInfo(timezone))
    except Exception:
        now = datetime.now(tz.utc)

    # Build 7-day reference so the model never has to do date arithmetic
    day_lines = []
    for i in range(7):
        d = now + timedelta(days=i)
        label = "Today" if i == 0 else "Tomorrow" if i == 1 else d.strftime("%A")
        day_lines.append(f"- {label}: {d.strftime('%A, %B %d, %Y')}")
    week_ref = "\n".join(day_lines)

    tz_info = _get_tz_info(timezone)
    system_prompt = ACTION_EXTRACTION_PROMPT.format(timezone=tz_info, week_ref=week_ref)

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


async def extract_run_context_from_conversation(
    messages: List[Dict[str, str]], timezone: str = "UTC"
) -> dict:
    """Extract runtime context (client name, email, etc.) for manual workflow execution."""
    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system="You are a context extraction system. Analyze the conversation and extract any runtime context the user provided for running a workflow — like client name, email, phone, appointment date, or notes. Use the extract_context tool to output the result. Only include fields that were explicitly mentioned.",
            messages=messages,
            tools=[CONTEXT_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_context"},
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_context":
                # Filter out empty values
                return {k: v for k, v in block.input.items() if v}
        return {}
    except Exception:
        return {}


SCHEDULE_EXTRACTION_TOOL = {
    "name": "extract_schedule",
    "description": "Extract the new schedule from the conversation for updating a workflow.",
    "input_schema": {
        "type": "object",
        "properties": {
            "cron_expression": {
                "type": "string",
                "description": "Standard 5-field cron expression (minute hour day_of_month month day_of_week)",
            },
            "schedule_description": {
                "type": "string",
                "description": "Human-readable schedule description (e.g., 'every Monday at 9am')",
            },
            "frequency": {
                "type": "string",
                "description": "Frequency label: daily, weekly, weekdays, etc.",
            },
        },
        "required": ["cron_expression", "schedule_description", "frequency"],
    },
}


async def extract_schedule_from_conversation(
    messages: List[Dict[str, str]], timezone: str = "UTC"
) -> Optional[dict]:
    """Extract a new schedule (cron expression + description) from the conversation."""
    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=(
                "You are a schedule extraction system. The user wants to change when a workflow runs. "
                "Analyze the conversation and extract the new schedule they described. "
                "Generate a valid 5-field cron expression and a human-readable description. "
                "Cron format: minute hour day_of_month month day_of_week. "
                "Examples: 'every morning at 9am' → cron '0 9 * * *', 'Mondays at 8am' → '0 8 * * 1'. "
                f"The user's timezone is {timezone}."
            ),
            messages=messages,
            tools=[SCHEDULE_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_schedule"},
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_schedule":
                return block.input
        return None
    except Exception:
        return None


EMAIL_FILTER_EXTRACTION_TOOL = {
    "name": "extract_email_filter",
    "description": "Extract Gmail filter criteria from the conversation for an email-triggered workflow.",
    "input_schema": {
        "type": "object",
        "properties": {
            "gmail_query": {
                "type": "string",
                "description": "Gmail search query (e.g., 'from:leads@example.com is:unread')",
            },
            "filter_description": {
                "type": "string",
                "description": "Human-readable description of the email filter (e.g., 'emails from new leads')",
            },
        },
        "required": ["gmail_query", "filter_description"],
    },
}


async def extract_email_filter_from_conversation(
    messages: List[Dict[str, str]],
) -> Optional[dict]:
    """Extract Gmail filter criteria from conversation using tool_use."""
    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=(
                "You are a Gmail filter extraction system. Analyze the conversation and extract "
                "the Gmail search query that matches the emails the user described. Use Gmail search "
                "operators: from:, to:, subject:, is:unread, label:, category:, has:attachment, etc. "
                "Always include 'is:unread' unless the user specifically wants to match read emails. "
                "Use the extract_email_filter tool to output the result."
            ),
            messages=messages,
            tools=[EMAIL_FILTER_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_email_filter"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_email_filter":
                return block.input

        return None
    except Exception:
        return None


WORKFLOW_EDIT_EXTRACTION_TOOL = {
    "name": "extract_workflow_edit",
    "description": "Extract the changes the user wants to make to a workflow's steps.",
    "input_schema": {
        "type": "object",
        "properties": {
            "step_updates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step_order": {
                            "type": "integer",
                            "description": "Which step to update (1-based)",
                        },
                        "new_description": {
                            "type": "string",
                            "description": "Updated plain-English description for this step",
                        },
                        "new_action_config": {
                            "type": "object",
                            "description": "Updated config (e.g., new subject, body, recipient)",
                        },
                    },
                    "required": ["step_order", "new_description"],
                },
            },
        },
        "required": ["step_updates"],
    },
}


async def extract_workflow_edit_from_conversation(
    messages: List[Dict[str, str]],
    workflow_steps: List[dict],
) -> Optional[dict]:
    """Extract workflow step edits from conversation using tool_use."""
    steps_desc = "\n".join(
        f"Step {s['step_order']}: [{s['action_type']}] {s['description']}"
        for s in workflow_steps
    )
    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=(
                "You are a workflow editor. The user wants to change what a workflow does. "
                "Given the current workflow steps and the conversation, extract the changes. "
                "Use the extract_workflow_edit tool to output the result.\n\n"
                f"Current workflow steps:\n{steps_desc}"
            ),
            messages=messages,
            tools=[WORKFLOW_EDIT_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_workflow_edit"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_workflow_edit":
                return block.input

        return None
    except Exception:
        return None


def match_workflow_by_name(db_workflows: list, name_query: str) -> Optional[object]:
    """Fuzzy-match a workflow by name. Returns the best match or None.

    Tries exact match first, then case-insensitive contains, then word overlap.
    """
    query_lower = name_query.lower().strip()

    # Exact match (case-insensitive)
    for wf in db_workflows:
        if wf.name.lower() == query_lower:
            return wf

    # Contains match
    for wf in db_workflows:
        if query_lower in wf.name.lower() or wf.name.lower() in query_lower:
            return wf

    # Word overlap — pick the workflow with the most overlapping words
    query_words = set(query_lower.split())
    best, best_score = None, 0
    for wf in db_workflows:
        wf_words = set(wf.name.lower().split())
        overlap = len(query_words & wf_words)
        if overlap > best_score:
            best, best_score = wf, overlap
    return best if best_score > 0 else None


PROVIDER_DISPLAY = {
    "gmail": {"name": "Gmail", "capabilities": "send emails"},
    "google_calendar": {"name": "Google Calendar", "capabilities": "create events, list events, and check availability"},
}


def _build_connection_status(connected_providers: Optional[List[str]] = None) -> str:
    """Build dynamic connection status string for the system prompt."""
    all_providers = set(PROVIDER_DISPLAY.keys())

    if connected_providers:
        connected_set = set(connected_providers) & all_providers
        disconnected = all_providers - connected_set
    else:
        connected_set = set()
        disconnected = all_providers

    parts = []
    if connected_set:
        names = [PROVIDER_DISPLAY[p]["name"] for p in sorted(connected_set)]
        caps = [PROVIDER_DISPLAY[p]["capabilities"] for p in sorted(connected_set)]
        parts.append(
            f"You ARE connected to the owner's {' and '.join(names)}. "
            f"You CAN {' and '.join(caps)}. "
            "NEVER say you can't do these things. "
            'NEVER say "I can\'t actually see your calendar" or "I don\'t have access" — you DO have access. '
            "Always use the appropriate hidden tags to execute the action. "
            "If an action fails, the system will tell you — do not preemptively claim you can't do something."
        )
    if disconnected:
        disc_names = [PROVIDER_DISPLAY[p]["name"] for p in sorted(disconnected)]
        disc_providers = [p for p in sorted(disconnected)]
        tool_examples = []
        for p in disc_providers:
            if p == "gmail":
                tool_examples.append("sending emails requires Gmail")
            elif p == "google_calendar":
                tool_examples.append("calendar actions require Google Calendar")
        parts.append(
            f"CRITICAL: You are NOT connected to: {', '.join(disc_names)}. "
            f"({', '.join(tool_examples)}). "
            "You CANNOT use disconnected tools. Do NOT attempt any action that requires a "
            "disconnected tool — do NOT start gathering fields (like asking for a subject line, "
            "recipient, event time, etc.) for an action that needs a disconnected tool. "
            "Instead, IMMEDIATELY suggest connecting it and include the <connect_tool> tag. "
            "For example, if Gmail is not connected and the user says 'send an email to X', "
            "respond with: 'To send that email, we'll need to connect your Gmail first. "
            "Click below to get that set up!' and include <connect_tool>gmail</connect_tool>."
        )
    elif not connected_set:
        parts.append(
            "CRITICAL: You are NOT connected to any tools yet. You CANNOT send emails, "
            "create events, or do anything that requires Gmail or Google Calendar. "
            "Do NOT start gathering fields for any action. Instead, IMMEDIATELY suggest "
            "connecting the needed tool and include the <connect_tool> tag."
        )

    return "\n".join(parts)


async def get_ai_response(
    messages: List[Dict[str, str]],
    timezone: str = "UTC",
    workflow_names: Optional[List[str]] = None,
    connected_providers: Optional[List[str]] = None,
) -> str:
    """Send messages to Claude and return the assistant's response."""
    from datetime import datetime, timezone as tz

    from datetime import timedelta
    from zoneinfo import ZoneInfo
    try:
        now = datetime.now(ZoneInfo(timezone))
    except Exception:
        now = datetime.now(tz.utc)
    today = now.strftime("%A, %B %d, %Y")
    tz_info = _get_tz_info(timezone)

    # Build a 7-day reference so the AI doesn't have to do date math
    day_lines = []
    for i in range(7):
        d = now + timedelta(days=i)
        label = "Today" if i == 0 else "Tomorrow" if i == 1 else d.strftime("%A")
        day_lines.append(f"- {label}: {d.strftime('%A, %B %d, %Y')}")
    week_ref = "\n".join(day_lines)

    # Inject dynamic connection status into the prompt
    connection_status = _build_connection_status(connected_providers)
    prompt = SYSTEM_PROMPT.replace("{connection_status}", connection_status)

    system = prompt + f"\n\nToday's date is {today}. The user's timezone is {tz_info}.\n\nUpcoming days for reference:\n{week_ref}"

    if workflow_names:
        wf_list = ", ".join(f'"{n}"' for n in workflow_names)
        system += f"\n\nThe owner currently has these saved processes: {wf_list}. " \
                  "Use the exact name when referencing them in <workflow_manage>, " \
                  "<workflow_status>, <workflow_run>, and <workflow_schedule> tags. " \
                  "You CAN list these workflows (<workflow_list>), check their activity " \
                  "(<workflow_status>), show recent system activity (<workflow_activity>), " \
                  "run them manually (<workflow_run>), and change their schedule " \
                  "(<workflow_schedule>). NEVER say you can't do these things."
    else:
        system += "\n\nThe owner has no saved processes yet. If they ask to see their workflows, " \
                  "still use <workflow_list>true</workflow_list> — the system will show an empty state."

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
