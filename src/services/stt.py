import asyncio
import base64
import logging
import os
import uuid

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v1.types import (
    ListenV1Results,
    ListenV1UtteranceEnd,
)
from dotenv import load_dotenv
from src.chat.chat_services import chat_with_history
from src.services.tts import generate_speech
from twilio.rest import Client

load_dotenv()

logger = logging.getLogger(__name__)

api_key = os.getenv("DEEPGRAM_API_KEY")

if not api_key:
    raise ValueError("DEEPGRAM_API_KEY not found in .env")

dg_client = AsyncDeepgramClient(api_key=api_key)


async def process_transcript(transcript, websocket, stream_info, playback_lock):
    try:
        logger.info("[USER]: %s", transcript)

        session_id = stream_info.get("session_id")

        if not session_id:
            logger.error("[RAG] Session ID not available")
            return

        result = await chat_with_history(session_id, transcript)
        answer = result["answer"]
        end_call = result.get("end_call", False)

        logger.info("[RAG] Answer: %s", answer)

        logger.info("[ELEVENLABS] Generating audio...")

        audio_bytes = await asyncio.to_thread(generate_speech, answer)

        logger.info("[ELEVENLABS] Audio generated!")

        stream_sid = stream_info.get("stream_sid")

        if not stream_sid:
            logger.error("[TWILIO] Stream SID not available")
            return

        async with playback_lock:
            # Send audio to Twilio
            for i in range(0, len(audio_bytes), 160):
                chunk = audio_bytes[i : i + 160]

                payload = base64.b64encode(chunk).decode("ascii")

                await websocket.send_json(
                    {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": payload},
                    }
                )

                await asyncio.sleep(0.02)

            logger.info("[TWILIO] Audio sent for playback!")

            # End call only after goodbye audio has finished playing
            if end_call:
                call_sid = stream_info.get("call_sid")

                if not call_sid:
                    logger.error("[TWILIO] Call SID not available")
                    return

                account_sid = os.getenv("TWILIO_ACCOUNT_SID")
                auth_token = os.getenv("TWILIO_AUTH_TOKEN")

                if not account_sid or not auth_token:
                    logger.error("[TWILIO] Credentials not configured")
                    return

                # Create a unique mark for this goodbye audio
                mark_name = f"goodbye-{uuid.uuid4().hex}"

                loop = asyncio.get_running_loop()
                mark_future = loop.create_future()

                stream_info["pending_mark"] = {
                    "name": mark_name,
                    "future": mark_future,
                }

                try:
                    # Ask Twilio to acknowledge when playback finishes
                    await websocket.send_json(
                        {
                            "event": "mark",
                            "streamSid": stream_sid,
                            "mark": {"name": mark_name},
                        }
                    )

                    logger.info("[TWILIO] Waiting for goodbye playback to finish...")

                    await asyncio.wait_for(mark_future, timeout=60)

                    logger.info("[TWILIO] Goodbye audio finished playing!")

                    # End the active call
                    client = Client(account_sid, auth_token)

                    await asyncio.to_thread(
                        client.calls(call_sid).update, status="completed"
                    )

                    logger.info("[TWILIO] Call ended successfully!")

                except asyncio.TimeoutError:  # noqa: UP041
                    logger.error("[TWILIO] Playback acknowledgment timed out")

                finally:
                    stream_info.pop("pending_mark", None)

    except Exception:
        logger.exception("[VOICE PIPELINE] Error processing transcript")


def register_transcription_events(connection, websocket, stream_info):

    playback_lock = asyncio.Lock()
    transcript_buffer = []

    def on_transcript(message):

        if isinstance(message, ListenV1UtteranceEnd):
            if transcript_buffer:
                complete_transcript = " ".join(transcript_buffer)
                transcript_buffer.clear()

                logger.info("[COMPLETE TRANSCRIPT]: %s", complete_transcript)

                asyncio.create_task(
                    process_transcript(
                        complete_transcript, websocket, stream_info, playback_lock
                    )
                )

            return

        if not isinstance(message, ListenV1Results):
            return

        if not message.channel or not message.channel.alternatives:
            return

        transcript = message.channel.alternatives[0].transcript.strip()

        if not transcript:
            return

        if message.is_final:
            transcript_buffer.append(transcript)

            if getattr(message, "speech_final", False):
                complete_transcript = " ".join(transcript_buffer)
                transcript_buffer.clear()

                logger.info("[COMPLETE TRANSCRIPT]: %s", complete_transcript)

                asyncio.create_task(
                    process_transcript(
                        complete_transcript, websocket, stream_info, playback_lock
                    )
                )

        else:
            logger.debug("[INTERIM]: %s", transcript)

    connection.on(EventType.MESSAGE, on_transcript)

    connection.on(
        EventType.ERROR, lambda error: logger.error("[DEEPGRAM ERROR]: %s", error)
    )

    connection.on(EventType.OPEN, lambda _: logger.info("[DEEPGRAM] Connected"))

    connection.on(EventType.CLOSE, lambda _: logger.info("[DEEPGRAM] Disconnected"))
