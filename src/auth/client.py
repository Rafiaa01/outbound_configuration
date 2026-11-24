from openai import AsyncOpenAI, api_key
from src.auth.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
from twilio.rest import Client

client = Client(
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN
)

client = AsyncOpenAI(api_key=api_key)