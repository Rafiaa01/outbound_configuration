import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("app")

from src.routes.twilio_setup import router as twilio_router

application = FastAPI(
    title="Twilio Audio Streaming",
    description="Receive live phone call audio chunks from Twilio",
    version="1.0.0",
)
application.include_router(twilio_router, prefix="/twilio", tags=["Twilio"])


@application.on_event("startup")
async def startup_checks():
    log.info("Server starting. PUBLIC_HOST=%s", os.getenv("PUBLIC_HOST", "(not set)"))
    for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "DEEPGRAM_API_KEY"):
        log.info("%s is %s", key, "set" if os.getenv(key) else "MISSING")


@application.middleware("http")
async def log_requests(request: Request, call_next):
    """Logs every HTTP request, so we can see whether Twilio reaches the server at all."""
    started = time.time()
    response = await call_next(request)
    log.info("HTTP %s %s -> %s (%.0f ms)", request.method, request.url.path,
             response.status_code, (time.time() - started) * 1000)
    return response


@application.get("/")
async def root():
    return {"message": "Twilio Audio Streaming Server is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.application:application",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=True,
    )
