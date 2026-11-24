# Twilio Outbound Calling

## Overview

The `outbound.py` file initiates outbound phone calls using the Twilio REST API.

It connects to your Twilio account using credentials stored in the `.env` file. When a call is initiated, Twilio calls the recipient and executes the provided TwiML instructions to establish a WebSocket connection with the FastAPI server.

## How It Works

1. Loads Twilio credentials from `.env`.
2. Initializes the Twilio client using Account SID and Auth Token.
3. Calls `client.calls.create()` with:
   - Recipient phone number (`to`)
   - Twilio phone number (`from_`)
   - TwiML instructions
4. Twilio initiates the outbound call.
5. When the recipient answers, Twilio connects to the FastAPI WebSocket endpoint.
6. The WebSocket receives audio events (`connected`, `start`, `media`, and `stop`).

Currently, the WebSocket receives and logs incoming audio chunks. AI speech processing and audio responses are not implemented yet.

## Environment Variables

Create a `.env` file in the project root:

```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number

APP_HOST=0.0.0.0
APP_PORT=8000
```

## How to Run

**1. Install dependencies**

```bash
pip install twilio fastapi uvicorn python-dotenv
```

**2. Start the FastAPI server**

Open Terminal 1:

```bash
uvicorn app.main:application --host 0.0.0.0 --port 8000 --reload
```

**3. Start the VS Code Dev Tunnel**

Make sure port `8000` is publicly accessible and the tunnel remains active.

**4. Configure the WebSocket URL in `outbound.py`**

```text
wss://YOUR-TUNNEL-URL/twilio/media
```

**5. Initiate the outbound call**

Open Terminal 2:

```bash
python outbound.py
```

The recipient's phone should ring.
