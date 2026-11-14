"""SecondLook web server: JSON + Server-Sent Events API around the agent pipeline, and the static web UI.

Run:  AWS_PROFILE=team10 .venv/bin/uvicorn server:app --port 8000
"""
import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import aws
from src.analytics import exposures, goal_buckets, macro_context, portfolio_risk, provenance, risk_units
from src.analytics import CAPACITY_RULES, TOLERANCE_CAP
from src.bedrock import DEFAULT_MODEL
from src.errors import friendly
from src.orchestrator import run
from src.universe import UNIVERSE

ROOT = Path(__file__).parent
ORDER = ["robert", "amira", "mateo", "maya"]
PERSONAS = {p.stem: json.loads(p.read_text()) for p in (ROOT / "personas").glob("*.json")}
PERSONAS = {k: PERSONAS[k] for k in sorted(PERSONAS, key=lambda k: ORDER.index(k) if k in ORDER else 99)}

app = FastAPI(title="SecondLook")
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


def _dump(obj):
    return json.dumps(obj, default=str)


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/meta")
def meta():
    cfg = aws._cfg()
    return {"model": DEFAULT_MODEL, "bucket": cfg["bucket"], "guardrail_id": cfg["guardrail_id"],
            "provenance": provenance(), "macro": macro_context(),
            "capacity_rules": CAPACITY_RULES, "tolerance_caps": TOLERANCE_CAP,
            "risk_units": risk_units(),
            "universe": {t: {"name": m["name"], "asset_class": m["asset_class"], "sector": m.get("starter_sector")}
                         for t, m in UNIVERSE.items()}}


@app.get("/api/personas")
def personas():
    out = []
    for pid, p in PERSONAS.items():
        h = p["holdings"]
        out.append({**p, "baseline": {"exposures": exposures(h), "goals": goal_buckets(p, h), "risk": portfolio_risk(h)},
                    "holding_names": {x["ticker"]: UNIVERSE[x["ticker"]]["name"] for x in h}})
    return out


@app.get("/api/trace/{run_id}")
def trace(run_id: str):
    """Re-open a past analysis from its S3 audit record (falls back to the local runs/ folder)."""
    if not run_id.isalnum():
        raise HTTPException(400, "That run ID isn't valid.")
    local = ROOT / "runs" / f"{run_id}.json"
    t = json.loads(local.read_text()) if local.exists() else aws.load_trace(run_id)
    if not t:
        raise HTTPException(404, "No saved analysis with that run ID.")
    return t


class AnalyzeIn(BaseModel):
    persona_id: str
    request: str


def _stream_run(persona, request):
    q: queue.Queue = queue.Queue()

    def work():
        try:
            trace = run(persona, request, on_step=lambda s: q.put(("step", {"label": s})))
            q.put(("result", trace))
        except Exception as e:  # surface a readable error to the UI instead of hanging
            q.put(("error", friendly(e)))
        q.put(None)

    threading.Thread(target=work, daemon=True).start()
    while True:
        item = q.get()
        if item is None:
            break
        ev, data = item
        yield f"event: {ev}\ndata: {_dump(data)}\n\n"


@app.post("/api/analyze")
def analyze(body: AnalyzeIn):
    if body.persona_id not in PERSONAS:
        raise HTTPException(404, "That investor profile doesn't exist. Reload the page.")
    if not body.request.strip():
        raise HTTPException(400, "Type an idea first, or pick one of the suggestions.")
    if len(body.request) > 1000:
        raise HTTPException(400, "That's too long. Describe the idea in a sentence or two.")
    return StreamingResponse(_stream_run(PERSONAS[body.persona_id], body.request), media_type="text/event-stream")


class CompareIn(BaseModel):
    request: str


@app.post("/api/compare")
def compare(body: CompareIn):
    def gen():
        q: queue.Queue = queue.Queue()

        def one(pid):
            try:
                q.put(("result", {"persona_id": pid, "trace": run(PERSONAS[pid], body.request)}))
            except Exception as e:
                q.put(("error", {"persona_id": pid, **friendly(e)}))

        with ThreadPoolExecutor(len(PERSONAS)) as ex:
            for pid in PERSONAS:
                ex.submit(one, pid)
            for _ in PERSONAS:
                ev, data = q.get()
                yield f"event: {ev}\ndata: {_dump(data)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
