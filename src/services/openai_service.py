import os

from dotenv import load_dotenv
from src.auth.client import client

load_dotenv()



api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env")


async def generate_response(user_text: str) -> str:
    """Send a transcript to OpenAI and return its response."""

    response = await client.responses.create(
        model="gpt-4o-mini",
        instructions=(
            "You are a helpful AI voice assistant. "
            "Keep your answers natural, conversational, and concise "
            "because they will be spoken aloud."
        ),
        input=user_text,
    )

    return response.output_text
