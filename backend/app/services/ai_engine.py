from typing import List, Dict
from anthropic import AsyncAnthropic
from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = (
    "You are AImplify, a friendly AI business assistant that helps small business "
    "owners automate their repetitive tasks. You speak in plain, simple language. "
    "You never use technical jargon. You are patient and helpful."
)


async def get_ai_response(messages: List[Dict[str, str]]) -> str:
    """Send messages to Claude and return the assistant's response."""
    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text
