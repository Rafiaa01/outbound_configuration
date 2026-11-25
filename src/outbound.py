"""
Start an outbound call and log every step, so a failure shows exactly where it breaks.

Usage (from the project root):
    python -m src.outbound +923001234567
or set RECIPIENT_NUMBER in .env and run:
    python -m src.outbound
"""

import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("outbound")

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "0zmgw9cz-8000.inc1.devtunnels.ms")  # no https://

STREAM_URL = f"wss://{PUBLIC_HOST}/twilio/media"
STATUS_URL = f"https://{PUBLIC_HOST}/twilio/call-status"
FINAL_STATUSES = {"completed", "busy", "failed", "no-answer", "canceled"}


def mask(value: str) -> str:
    return value[:4] + "..." + value[-4:] if len(value) > 8 else "(missing)"


def check_env(recipient: str) -> bool:
    log.info("---- 1. Checking .env ----")
    ok = True
    log.info("TWILIO_PHONE_NUMBER = %s", TWILIO_NUMBER or "(missing)")
    log.info("Recipient           = %s", recipient or "(missing)")
    log.info("Stream URL          = %s", STREAM_URL)
    if not ACCOUNT_SID.startswith("AC"):
        log.error("TWILIO_ACCOUNT_SID is missing or does not start with 'AC'")
        ok = False
    if not AUTH_TOKEN:
        log.error("TWILIO_AUTH_TOKEN is missing")
        ok = False
    for name, number in (("TWILIO_PHONE_NUMBER", TWILIO_NUMBER), ("Recipient", recipient)):
        if not number.startswith("+"):
            log.error("%s must be in +countrycode format, e.g. +923001234567 (got %r)", name, number)
            ok = False
    return ok


def check_twilio_account(client: Client, recipient: str) -> bool:
    log.info("---- 2. Checking Twilio account ----")
    try:
        account = client.api.v2010.accounts(ACCOUNT_SID).fetch()
    except TwilioRestException as e:
        log.error("Could not log in to Twilio (code %s): %s", e.code, e.msg)
        log.error("-> Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env")
        return False
    log.info("Account '%s': status=%s, type=%s", account.friendly_name, account.status, account.type)
    if account.status != "active":
        log.error("Account is not active (status=%s)", account.status)
        return False

    owned = client.incoming_phone_numbers.list(phone_number=TWILIO_NUMBER, limit=1)
    if owned:
        log.info("Caller number %s belongs to this account", TWILIO_NUMBER)
    else:
        log.error("TWILIO_PHONE_NUMBER %s is NOT a number on this account", TWILIO_NUMBER)
        return False

    if account.type == "Trial":
        verified = client.outgoing_caller_ids.list(phone_number=recipient, limit=1)
        if verified:
            log.info("Trial account: recipient %s is verified", recipient)
        else:
            log.error("Trial account: recipient %s is NOT a verified caller ID", recipient)
            log.error("-> Twilio Console > Phone Numbers > Verified Caller IDs > add this number")
            return False
    return True


def check_tunnel() -> None:
    log.info("---- 3. Checking the tunnel / server ----")
    url = f"https://{PUBLIC_HOST}/"
    try:
        r = requests.get(url, timeout=8)
        log.info("GET %s -> HTTP %s", url, r.status_code)
        if r.status_code != 200 or "running" not in r.text.lower():
            log.warning("Tunnel answered but not with our server's message. Is the tunnel PUBLIC "
                        "and is uvicorn running on port 8000? Body starts: %r", r.text[:120])
        else:
            log.info("Server is reachable through the tunnel")
    except requests.RequestException as e:
        log.warning("Tunnel not reachable: %s", e)
        log.warning("-> The phone may still ring, but the audio stream will fail after answering")


def place_call(client: Client, recipient: str) -> str | None:
    log.info("---- 4. Placing the call ----")
    twiml = f"""<Response>
    <Say>Connecting you to the voice bot.</Say>
    <Connect>
        <Stream url="{STREAM_URL}" />
    </Connect>
</Response>"""
    try:
        call = client.calls.create(
            to=recipient,
            from_=TWILIO_NUMBER,
            twiml=twiml,
            status_callback=STATUS_URL,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
            time_limit=120,
              # Answering Machine Detection
            machine_detection="Enable",
        )
    except TwilioRestException as e:
        log.error("Twilio REFUSED to create the call")
        log.error("  HTTP status : %s", e.status)
        log.error("  Error code  : %s", e.code)
        log.error("  Message     : %s", e.msg)
        log.error("  Details     : %s", e.more_info)
        return None
    log.info("Call created: SID=%s, status=%s", call.sid, call.status)
    return call.sid


def watch_call(client: Client, call_sid: str, timeout_s: int = 90) -> None:
    log.info("---- 5. Watching call status (Ctrl+C to stop) ----")
    last = None
    start = time.time()
    while time.time() - start < timeout_s:
        call = client.calls(call_sid).fetch()
        if call.status != last:
            log.info("Status: %s", call.status)
            last = call.status
        if call.status in FINAL_STATUSES:
            log.info("Final status=%s, duration=%ss, answered_by=%s",
                     call.status, call.duration, call.answered_by)
            show_call_errors(client, call_sid)
            return
        time.sleep(2)
    log.info("Still %s after %ss; stopped watching", last, timeout_s)


def show_call_errors(client: Client, call_sid: str) -> None:
    try:
        notes = client.api.v2010.accounts(ACCOUNT_SID).calls(call_sid).notifications.list(limit=20)
    except Exception as e:  # notifications are optional; never crash here  # noqa: BLE001
        log.info("(Could not read call notifications: %s)", e)
        return
    if not notes:
        log.info("Twilio logged no errors or warnings for this call")
    for n in notes:
        log.error("Twilio error %s: %s", n.error_code, n.message_text)
    log.info("Full log: https://console.twilio.com/us1/monitor/logs/calls?sid=%s", call_sid)


def main():
    recipient = sys.argv[1] if len(sys.argv) > 1 else os.getenv("RECIPIENT_NUMBER", "")
    if not check_env(recipient):
        sys.exit(1)
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    if not check_twilio_account(client, recipient):
        sys.exit(1)
    check_tunnel()
    call_sid = place_call(client, recipient)
    if call_sid:
        watch_call(client, call_sid)


if __name__ == "__main__":
    main()
