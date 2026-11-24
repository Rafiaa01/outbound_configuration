import asyncio
import base64
import json
import logging
import os

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from src.services.stt import (
    dg_client,
    register_transcription_events,
)

router = APIRouter()
log = logging.getLogger("twilio")

PUBLIC_HOST = os.getenv("PUBLIC_HOST", "0zmgw9cz-8000.inc1.devtunnels.ms")


@router.post("/voice")
async def voice(request: Request):
    form = await request.form()

    log.info(
        "[voice] CallSid=%s From=%s AnsweredBy=%s",
        form.get("CallSid"),
        form.get("From"),
        form.get("AnsweredBy"),
    )
    twiml = f"""<Response>
        <Connect>
            <Stream url="wss://{PUBLIC_HOST}/twilio/media" />
        </Connect>
    </Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/call-status")
async def call_status(request: Request):
    form = await request.form()

    log.info(
        "[status] call=%s status=%s to=%s duration=%s",
        form.get("CallSid"),
        form.get("CallStatus"),
        form.get("To"),
        form.get("CallDuration"),
    )

    return Response(status_code=204)


@router.websocket("/media")
async def media_stream(websocket: WebSocket):

    await websocket.accept()
    log.info("[media] WebSocket accepted")

    chunks = 0
    stream_sid = None
    listener_task = None
    stream_info = {"stream_sid": None}
    try:
        async with dg_client.listen.v1.connect(
            model="nova-3",
            encoding="mulaw",
            sample_rate=8000,
            channels=1,
            interim_results=True,
            smart_format=True,
            punctuate=True,
        ) as dg_connection:
            log.info("[DEEPGRAM] Connection created")

            register_transcription_events(
            dg_connection,
            websocket,
            stream_info
        )
            listener_task = asyncio.create_task(dg_connection.start_listening())

            log.info("[DEEPGRAM] Listening started")

            while True:
                data = json.loads(await websocket.receive_text())

                event = data.get("event")

                if event == "connected":
                    log.info("[media] Twilio connected")

                elif event == "start":
                    start = data["start"]
                    stream_sid = start["streamSid"]
                    call_sid = start.get("callSid")
                    
                    # Save Stream SID for sending audio back to Twilio
                    stream_info["stream_sid"] = stream_sid
                    
                    log.info("[media] Stream started")
                    log.info("[media] Call SID: %s", call_sid)
                    log.info("[media] Stream SID: %s", stream_sid)
                    log.info("[media] Stream started: %s", stream_sid)

                    log.info("[media] Audio format: %s", start.get("mediaFormat"))

                elif event == "media":
                    chunks += 1

                    # Decode Twilio's Base64 audio payload
                    payload = data["media"]["payload"]
                    audio_bytes = base64.b64decode(payload)

                    # Send audio bytes to Deepgram
                    await dg_connection.send_media(audio_bytes)

                    if chunks == 1:
                        log.info("[media] First audio chunk sent to Deepgram")

                    elif chunks % 50 == 0:
                        log.info("[media] %s chunks forwarded", chunks)

                elif event == "stop":
                    log.info("[media] Stream stopped after %s chunks", chunks)

                    await dg_connection.send_finalize()
                    break

    except WebSocketDisconnect:
        log.warning("[media] Twilio disconnected after %s chunks", chunks)

    except Exception:
        log.exception("[media] Streaming error (streamSid=%s)", stream_sid)

    finally:
        if listener_task and not listener_task.done():
            listener_task.cancel()

            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        log.info("[media] Stream handler finished")
