import os

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

api_key = os.getenv("ELEVENLABS_API_KEY")

if not api_key:
    raise ValueError("ELEVENLABS_API_KEY not found in .env")

client = ElevenLabs(api_key=api_key)


def generate_speech(text: str) -> bytes:
    """Convert text into speech using ElevenLabs."""

    audio = client.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_multilingual_v2",
        output_format="ulaw_8000",
    )

    return b"".join(audio)
