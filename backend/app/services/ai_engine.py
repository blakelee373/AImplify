from typing import List, Dict
from anthropic import AsyncAnthropic

from app.config import ANTHROPIC_API_KEY

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = (
    "You are AImplify, a friendly AI business assistant that helps small business owners "
    "automate their repetitive tasks. You speak in plain, simple language. You never use "
    "technical jargon. You are patient and helpful."
)


async def get_ai_response(messages: List[Dict[str, str]]) -> str:
    """Send conversation history to Claude and return the assistant's reply."""
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text
