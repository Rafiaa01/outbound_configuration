
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from src.routes.twilio_setup import router as twilio_router

load_dotenv()

application = FastAPI(
    title="Twilio Audio Streaming",
    description="Receive live phone call audio chunks from Twilio",
    version="1.0.0"
)

# Register Twilio routes
application.include_router(
    twilio_router,
    prefix="/twilio",
    tags=["Twilio"]
)


@application.get("/")
async def root():
    return {
        "message": "Twilio Audio Streaming Server is running"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=True
    )
