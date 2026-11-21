import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers import email_controller, escalation_controller, ticket_controller, user_controller
from app.core.config import get_settings
from app.core.database import init_db
from app.core.exceptions import AppError
from app.email_listener.imap_listener import ImapEmailListener
from app.email_listener.temp_inbox_listener import TempInboxListener

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.gmail_token_json:
        # Hosted: the token arrives as an env var; the Gmail client reads (and refreshes) it from this file.
        from pathlib import Path

        token = Path(settings.gmail_token_file)
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(settings.gmail_token_json)
    listeners = []
    if settings.email_listener_enabled:
        listeners.append(ImapEmailListener(settings))
    if settings.temp_inbox_enabled:
        app.state.temp_inbox = TempInboxListener(settings)
        listeners.append(app.state.temp_inbox)
    for listener in listeners:
        listener.start()
    if settings.triage_model == "sentinel_local":
        import threading

        from app.services.triage import get_triage_model

        threading.Thread(target=get_triage_model("sentinel_local").warm_up, name="triage-warmup", daemon=True).start()
    yield
    for listener in listeners:
        listener.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(ticket_controller.router)
app.include_router(email_controller.router)
app.include_router(escalation_controller.router)
app.include_router(user_controller.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
