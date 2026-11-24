
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/voice")
async def voice():
    """
    Twilio calls this endpoint when a call arrives.
    It instructs Twilio to open a bidirectional WebSocket.
    """

    twiml = """
    <Response>
        <Connect>
            <Stream url="wss://0zmgw9cz-8000.inc1.devtunnels.ms/twilio/media" />
        </Connect>
    </Response>
    """

    return Response(
        content=twiml,
        media_type="application/xml"
    )


@router.websocket("/media")
async def media_stream(websocket: WebSocket):

    await websocket.accept()

    print("Twilio WebSocket connected!")

    try:
        while True:

            message = await websocket.receive_text()
            data = json.loads(message)

            event = data.get("event")

            if event == "connected":
                print("Stream connected!")

            elif event == "start":
                print("Audio stream started!")

                print(
                    "Audio format:",
                    data["start"]["mediaFormat"]
                )

            elif event == "media":

                payload = data["media"]["payload"]

                print(
                    "Audio chunk received!",
                    "Payload length:",
                    len(payload)
                )

            elif event == "stop":
                print("Audio stream stopped!")

    except WebSocketDisconnect:
        print("Twilio WebSocket disconnected!")