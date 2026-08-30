"""The gateway every agent tool call routes through.

    POST /v1/authorize    agent submits a proposed tool call, gets a decision
    POST /v1/trips/run      runs one orchestrated trip in-process, live-streamed
    GET  /v1/events          SSE stream of every stage of every call, live
    GET  /v1/trips            the trip presets — what the dashboard's pills offer
    GET  /v1/transactions      trip-level records (input, agent order, status)
    GET  /v1/log                 the persisted audit ledger (page-load backfill)
    GET  /health                   liveness/readiness probe

Not /healthz: verified live on Cloud Run that this exact literal path
never reaches the container at all (no request in Cloud Run's own logs,
Google's generic edge 404 instead) while every other path, including
/health, passes through fine — Google's front end special-cases it.
/health is the same probe, just not on the reserved-looking path.

This is intentionally the only entry point. An agent that skips it and
calls a tool directly is exactly the failure mode Warden exists to close.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from warden import auth_token, events, triage
from warden.config import get_settings
from warden.guardrails import check_hard_limits
from warden.ledger import get_ledger
from warden.models import AuditRecord, Decision, ReviewResult, ToolCallRequest
from warden.registry import InMemoryRegistry, get_registry
from warden.reviewer_agent import _active_model_armor_template, review
from warden.transactions import get_store

app = FastAPI(title="Warden", version="0.1.0")

_registry = get_registry()
_ledger = get_ledger()
_transactions = get_store()

if isinstance(_registry, InMemoryRegistry):
    # Local dev has no shared store between processes — seed the demo fleet's
    # scopes on boot so `python demo/run_demo.py` works immediately against a
    # freshly started gateway. Cloud deployments use scripts/seed_registry.py
    # to write the same scopes into Firestore once, instead.
    from demo.scopes import DEMO_SCOPES

    for scope in DEMO_SCOPES:
        _registry.register(scope)

_dashboard_dir = Path(__file__).resolve().parent.parent / "dashboard" / "static"
if _dashboard_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_dashboard_dir)), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(str(_dashboard_dir / "index.html"))


def _process_call(
    request: ToolCallRequest,
    *,
    label: str | None = None,
    traveler_copy: str | None = None,
    transaction_id: str | None = None,
) -> dict:
    """The actual gateway logic — shared by /v1/authorize and every step
    warden/orchestrator.py runs.

    Publishes a warden.events entry at every stage, not just the final
    decision, tagged with `transaction_id` when this call is part of an
    orchestrated trip, so the dashboard can group live events under the
    right transaction instead of just a flat call-by-call feed.
    """
    settings = get_settings()
    call_id = events.new_call_id()

    events.publish({
        "call_id": call_id, "transaction_id": transaction_id, "stage": "intercept",
        "label": label, "traveler_copy": traveler_copy,
        "agent_id": request.agent_id, "tool": request.tool,
        "args": request.args, "reason": request.reason,
    })

    scope = _registry.get(request.agent_id)
    events.publish({
        "call_id": call_id, "transaction_id": transaction_id, "stage": "registry",
        "status": "found" if scope else "not_found", "agent_id": request.agent_id,
    })

    events.publish({"call_id": call_id, "transaction_id": transaction_id, "stage": "guardrail", "status": "checking"})
    hard_limit = check_hard_limits(request, scope)

    if hard_limit is not None:
        events.publish({
            "call_id": call_id, "transaction_id": transaction_id, "stage": "guardrail",
            "status": "fired", "detail": hard_limit.rationale,
        })
        result = hard_limit
    else:
        events.publish({"call_id": call_id, "transaction_id": transaction_id, "stage": "guardrail", "status": "pass"})

        triage_model = settings.ollama_triage_model if settings.model_backend == "ollama" else settings.gemma_model
        events.publish({
            "call_id": call_id, "transaction_id": transaction_id, "stage": "triage",
            "status": "checking", "model": triage_model,
        })
        fast_path = triage.quick_check(request, scope)
        events.publish({"call_id": call_id, "transaction_id": transaction_id, "stage": "triage", "status": fast_path})

        if fast_path == "safe":
            result = ReviewResult(
                decision=Decision.ALLOW,
                rationale="Cleared by Gemma triage — plainly in scope.",
                reviewed_by="gemma-triage",
            )
        else:
            review_model = settings.ollama_review_model if settings.model_backend == "ollama" else settings.gemini_model
            events.publish({
                "call_id": call_id, "transaction_id": transaction_id, "stage": "review",
                "status": "checking", "model": review_model,
                "model_armor_template": _active_model_armor_template(),
            })
            result = review(request, scope)
            events.publish({
                "call_id": call_id, "transaction_id": transaction_id, "stage": "review",
                "status": "done", "reviewed_by": result.reviewed_by,
                "model_armor_template": result.model_armor_template,
            })

    token = None
    if result.decision == Decision.ALLOW:
        token = auth_token.sign_token(
            agent_id=request.agent_id, tool=request.tool, decision=result.decision.value
        )

    events.publish({
        "call_id": call_id, "transaction_id": transaction_id, "stage": "decision",
        "decision": result.decision.value, "rationale": result.rationale,
        "reviewed_by": result.reviewed_by, "token": token,
        "model_armor_template": result.model_armor_template,
    })

    record = AuditRecord(
        agent_id=request.agent_id,
        tool=request.tool,
        args=request.args,
        decision=result.decision,
        rationale=result.rationale,
        reviewed_by=result.reviewed_by,
        model_armor_template=result.model_armor_template,
        token=token,
    )
    _ledger.append(record)

    events.publish({
        "call_id": call_id, "transaction_id": transaction_id, "stage": "ledger",
        "status": "recorded", "hash": record.hash, "prev_hash": record.prev_hash,
        "record": record.model_dump(),
    })

    return {
        "call_id": call_id,
        "decision": result.decision.value,
        "rationale": result.rationale,
        "reviewed_by": result.reviewed_by,
        "model_armor_template": result.model_armor_template,
        "token": token,
    }


@app.post("/v1/authorize")
def authorize(request: ToolCallRequest) -> dict:
    return _process_call(request)


@app.get("/v1/events")
async def sse_events():
    q = events.subscribe()

    async def gen():
        try:
            while True:
                event = await run_in_threadpool(q.get)
                yield f"data: {json.dumps(event, default=str)}\n\n"
        finally:
            events.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/v1/trips")
def list_trips() -> list[dict]:
    """What the dashboard's pills offer — one source of truth, same
    presets the CLI (`python -m demo.run_demo`) uses."""
    from demo.trips import TRIP_PRESETS

    return list(TRIP_PRESETS.values())


_demo_lock = threading.Lock()
_demo_running = False


class RunTripRequest(BaseModel):
    preset_id: str


@app.post("/v1/trips/run")
def run_trip_endpoint(body: RunTripRequest, background_tasks: BackgroundTasks, response: Response) -> dict:
    """Triggered by clicking a trip pill in the dashboard. Runs
    warden/orchestrator.py's run_trip() in-process as a background task —
    the dashboard watches it happen over /v1/events, not this response.

    Rejects a second run while one's in flight — two runs' events
    interleaved on the same stream is genuinely confusing to watch,
    confirmed while testing an earlier version of this endpoint.
    """
    from demo.trips import TRIP_PRESETS

    if body.preset_id not in TRIP_PRESETS:
        raise HTTPException(status_code=404, detail=f"Unknown trip preset {body.preset_id!r}")

    global _demo_running
    with _demo_lock:
        if _demo_running:
            response.status_code = 409
            return {"status": "already_running"}
        _demo_running = True

    def _run() -> None:
        global _demo_running
        from warden.orchestrator import run_trip

        try:
            run_trip(body.preset_id)
        finally:
            with _demo_lock:
                _demo_running = False

    background_tasks.add_task(_run)
    return {"status": "started", "preset_id": body.preset_id}


@app.get("/v1/transactions")
def list_transactions() -> list[dict]:
    return [t.model_dump() for t in _transactions.all()]


@app.get("/v1/log")
def log() -> list[dict]:
    return [r.model_dump() for r in _ledger.all()]
