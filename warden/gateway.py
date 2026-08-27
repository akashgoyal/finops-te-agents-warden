"""The gateway every agent tool call routes through.

    POST /v1/authorize   agent submits a proposed tool call, gets a decision
    POST /v1/demo/run     runs demo/scenarios.py in-process, live-streamed
    GET  /v1/events        SSE stream of every stage of every call, live
    GET  /v1/log            the persisted audit ledger (page-load backfill)
    GET  /healthz            Cloud Run readiness probe

This is intentionally the only entry point. An agent that skips it and
calls a tool directly is exactly the failure mode Warden exists to close.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from warden import auth_token, events, triage
from warden.config import get_settings
from warden.guardrails import check_hard_limits
from warden.ledger import get_ledger
from warden.models import AuditRecord, Decision, ReviewResult, ToolCallRequest
from warden.registry import InMemoryRegistry, get_registry
from warden.reviewer_agent import review

app = FastAPI(title="Warden", version="0.1.0")

_registry = get_registry()
_ledger = get_ledger()

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


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(str(_dashboard_dir / "index.html"))


def _process_call(
    request: ToolCallRequest, *, label: str | None = None, traveler_copy: str | None = None
) -> dict:
    """The actual gateway logic — shared by /v1/authorize and /v1/demo/run.

    Publishes a warden.events entry at every stage, not just the final
    decision, so the dashboard can render the call arriving, being checked,
    and being decided as three (or more) separate live moments instead of
    one opaque round trip.
    """
    settings = get_settings()
    call_id = events.new_call_id()

    events.publish({
        "call_id": call_id, "stage": "intercept", "label": label, "traveler_copy": traveler_copy,
        "agent_id": request.agent_id, "tool": request.tool,
        "args": request.args, "reason": request.reason,
    })

    scope = _registry.get(request.agent_id)

    events.publish({"call_id": call_id, "stage": "guardrail", "status": "checking"})
    hard_limit = check_hard_limits(request, scope)

    if hard_limit is not None:
        events.publish({"call_id": call_id, "stage": "guardrail", "status": "fired", "detail": hard_limit.rationale})
        result = hard_limit
    else:
        events.publish({"call_id": call_id, "stage": "guardrail", "status": "pass"})

        triage_model = settings.ollama_triage_model if settings.model_backend == "ollama" else settings.gemma_model
        events.publish({"call_id": call_id, "stage": "triage", "status": "checking", "model": triage_model})
        fast_path = triage.quick_check(request, scope)
        events.publish({"call_id": call_id, "stage": "triage", "status": fast_path})

        if fast_path == "safe":
            result = ReviewResult(
                decision=Decision.ALLOW,
                rationale="Cleared by Gemma triage — plainly in scope.",
                reviewed_by="gemma-triage",
            )
        else:
            review_model = settings.ollama_review_model if settings.model_backend == "ollama" else settings.gemini_model
            events.publish({"call_id": call_id, "stage": "review", "status": "checking", "model": review_model})
            result = review(request, scope)
            events.publish({"call_id": call_id, "stage": "review", "status": "done", "reviewed_by": result.reviewed_by})

    token = None
    if result.decision == Decision.ALLOW:
        token = auth_token.sign_token(
            agent_id=request.agent_id, tool=request.tool, decision=result.decision.value
        )

    events.publish({
        "call_id": call_id, "stage": "decision", "decision": result.decision.value,
        "rationale": result.rationale, "reviewed_by": result.reviewed_by, "token": token,
    })

    record = AuditRecord(
        agent_id=request.agent_id,
        tool=request.tool,
        args=request.args,
        decision=result.decision,
        rationale=result.rationale,
        reviewed_by=result.reviewed_by,
        token=token,
    )
    _ledger.append(record)

    events.publish({
        "call_id": call_id, "stage": "ledger", "status": "recorded",
        "hash": record.hash, "prev_hash": record.prev_hash, "record": record.model_dump(),
    })

    return {
        "call_id": call_id,
        "decision": result.decision.value,
        "rationale": result.rationale,
        "reviewed_by": result.reviewed_by,
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


_demo_lock = threading.Lock()
_demo_running = False


@app.post("/v1/demo/run")
def run_demo(background_tasks: BackgroundTasks, response: Response) -> dict:
    """Triggered by the dashboard's Run button. Runs demo/scenarios.py
    in-process (not over HTTP, unlike the CLI script) so each stage's
    event publishes without an extra network hop, and returns immediately
    — the actual run happens in a background task; the dashboard watches
    it happen over /v1/events, not this response.

    Rejects a second run while one's in flight — two runs' events
    interleaved on the same call_id stream is genuinely confusing to watch,
    confirmed while testing this by firing two before the first finished.
    """
    global _demo_running
    with _demo_lock:
        if _demo_running:
            response.status_code = 409
            return {"status": "already_running"}
        _demo_running = True

    from demo.scenarios import SCENARIOS

    run_id = events.new_call_id()

    def _run() -> None:
        global _demo_running
        try:
            events.publish({"type": "demo_run_started", "run_id": run_id})
            for step in SCENARIOS:
                request = ToolCallRequest(
                    agent_id=step["agent_id"], tool=step["tool"],
                    args=step["args"], reason=step["reason"],
                )
                _process_call(request, label=step["label"], traveler_copy=step["traveler_copy"])
                time.sleep(0.4)  # lets the UI render each stage instead of flashing by
        finally:
            events.publish({"type": "demo_run_finished", "run_id": run_id})
            with _demo_lock:
                _demo_running = False

    background_tasks.add_task(_run)
    return {"run_id": run_id, "status": "started"}


@app.get("/v1/log")
def log() -> list[dict]:
    return [r.model_dump() for r in _ledger.all()]
