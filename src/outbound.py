import os

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(account_sid, auth_token)


def make_outbound_call(recipient_number):

    twiml = """
    <Response>
        <Connect>
            <Stream url="wss://https://0zmgw9cz-8000.inc1.devtunnels.ms/media" />
        </Connect>
    </Response>
    """

    call = client.calls.create(
        to=recipient_number,
        from_=twilio_number,
        twiml=twiml
    )

    print("Call initiated!")
    print("Call SID:", call.sid)


if __name__ == "__main__":
    make_outbound_call("+923325898524")