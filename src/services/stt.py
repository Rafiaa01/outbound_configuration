
import os

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v1.types import ListenV1Results
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DEEPGRAM_API_KEY")

if not api_key:
    raise ValueError("DEEPGRAM_API_KEY not found in .env")

# Initialize Deepgram client
dg_client = AsyncDeepgramClient(api_key=api_key)


def on_transcript(message):

    if not isinstance(message, ListenV1Results):
        return

    if not message.channel or not message.channel.alternatives:
        return

    transcript = (
        message.channel.alternatives[0].transcript
    ).strip()

    if not transcript:
        return

    if message.is_final:
        print(f"\n[FINAL TRANSCRIPT]: {transcript}", flush=True)
    else:
        print(f"[INTERIM]: {transcript}", flush=True)


def register_transcription_events(connection):

    connection.on(EventType.MESSAGE, on_transcript)

    connection.on(
        EventType.ERROR,
        lambda error: print(f"[DEEPGRAM ERROR]: {error}", flush=True)
    )

    connection.on(
        EventType.OPEN,
        lambda _: print("[DEEPGRAM] Connected", flush=True)
    )

    connection.on(
        EventType.CLOSE,
        lambda _: print("[DEEPGRAM] Disconnected", flush=True)
    )
