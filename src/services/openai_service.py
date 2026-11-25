import os

from dotenv import load_dotenv
from src.auth.client import client
from src.prompt.assistant_prompt import EMPLOYEE_POLICY_ASSISTANT_PROMPT

load_dotenv()


api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env")


async def generate_response(user_text: str) -> str:
    """Send a transcript to OpenAI and return its response."""

    response = await client.responses.create(
        model="gpt-4o-mini",
        instructions=EMPLOYEE_POLICY_ASSISTANT_PROMPT,
        input=user_text,
    )

    return response.output_text
