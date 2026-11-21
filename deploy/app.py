"""SentinelDesk triage service (Cloud Run).

POST /triage {"subject": "...", "body": "..."} -> TriageModel.predict() JSON (triage/model.py, unchanged)
GET  /health                                  -> {"status": "ok", ...} once the model is loaded

The model is baked into the image at $MODEL_PATH (default /app/triage/models/triage.joblib) and loaded
once at startup, before the port opens, so Cloud Run only routes traffic to a warm instance.
"""
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from triage.model import TriageModel

MODEL_PATH = os.environ.get("MODEL_PATH", "/app/triage/models/triage.joblib")
MODEL_KIND = os.environ.get("MODEL_KIND", "lr")  # "lr" = TriageModel, "blend" = BlendModel (LR + kNN, ~0.6 s/ticket)
MAX_CHARS = int(os.environ.get("MAX_CHARS", "20000"))  # truncate huge pastes instead of failing

STATE: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.perf_counter()
    if MODEL_KIND == "blend":
        from triage.blend import BlendModel  # needs triage.joblib next to blend.joblib
        tm = BlendModel.load(MODEL_PATH)
    else:
        tm = TriageModel.load(MODEL_PATH)
    tm.predict("warm-up", "VPN is down for all users")  # first call pays numpy/scipy init cost
    STATE["model"] = tm
    STATE["load_s"] = round(time.perf_counter() - t0, 2)
    print(f"{MODEL_KIND} model loaded from {MODEL_PATH} in {STATE['load_s']}s", flush=True)
    yield
    STATE.clear()


app = FastAPI(title="SentinelDesk triage", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "OPTIONS"],
                   allow_headers=["*"])


class Ticket(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


@app.get("/health")
def health():
    if "model" not in STATE:
        raise HTTPException(503, "model not loaded")
    return {"status": "ok", "kind": MODEL_KIND, "model": os.path.basename(MODEL_PATH), "load_s": STATE["load_s"]}


@app.post("/triage")
def triage(t: Ticket):  # sync def -> runs in FastAPI's threadpool, keeps the event loop free
    subject = (t.subject or "")[:MAX_CHARS]
    body = (t.body or "")[:MAX_CHARS]
    if not subject.strip() and not body.strip():
        raise HTTPException(422, "subject or body is required")
    return STATE["model"].predict(subject, body)
