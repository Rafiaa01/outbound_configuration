
import asyncio
import base64
import logging
import os

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v1.types import ListenV1Results
from dotenv import load_dotenv
from src.services.openai_service import generate_response
from src.services.tts import generate_speech

load_dotenv()

logger = logging.getLogger(__name__)

api_key = os.getenv("DEEPGRAM_API_KEY")

if not api_key:
    raise ValueError("DEEPGRAM_API_KEY not found in .env")

dg_client = AsyncDeepgramClient(api_key=api_key)


async def process_transcript(transcript, websocket, stream_info, playback_lock):
    try:
        logger.info("[USER]: %s", transcript)

        answer = await generate_response(transcript)
        logger.info("[OPENAI RESPONSE]: %s", answer)

        logger.info("[ELEVENLABS] Generating audio...")

        # Run synchronous ElevenLabs SDK in a worker thread.
        audio_bytes = await asyncio.to_thread(generate_speech, answer)

        logger.info("[ELEVENLABS] Audio generated!")

        stream_sid = stream_info.get("stream_sid")

        if not stream_sid:
            logger.error("[TWILIO] Stream SID not available")
            return

        # Send audio to Twilio in 20 ms chunks.
        async with playback_lock:
            for i in range(0, len(audio_bytes), 160):
                chunk = audio_bytes[i:i + 160]
                payload = base64.b64encode(chunk).decode("ascii")

                await websocket.send_json({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": payload
                    }
                })

                await asyncio.sleep(0.02)

        logger.info("[TWILIO] Audio sent for playback!")

    except Exception:
        logger.exception("[VOICE PIPELINE] Error processing transcript")


def register_transcription_events(connection, websocket, stream_info):
    playback_lock = asyncio.Lock()

    def on_transcript(message):
        if not isinstance(message, ListenV1Results):
            return

        if not message.channel or not message.channel.alternatives:
            return

        transcript = message.channel.alternatives[0].transcript.strip()

        if not transcript:
            return

        if message.is_final:
            logger.info("[FINAL TRANSCRIPT]: %s", transcript)

            asyncio.create_task(
                process_transcript(
                    transcript,
                    websocket,
                    stream_info,
                    playback_lock
                )
            )
        else:
            logger.debug("[INTERIM]: %s", transcript)

    connection.on(EventType.MESSAGE, on_transcript)

    connection.on(
        EventType.ERROR,
        lambda error: logger.error("[DEEPGRAM ERROR]: %s", error)
    )

    connection.on(
        EventType.OPEN,
        lambda _: logger.info("[DEEPGRAM] Connected")
    )

    connection.on(
        EventType.CLOSE,
        lambda _: logger.info("[DEEPGRAM] Disconnected")
    )
