"""The gateway every agent tool call routes through.

    POST /v1/authorize   agent submits a proposed tool call, gets a decision
    GET  /v1/log          the audit ledger, for the live dashboard
    GET  /healthz         Cloud Run readiness probe

This is intentionally the only entry point. An agent that skips it and
calls a tool directly is exactly the failure mode Warden exists to close.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from warden import auth_token, triage
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


@app.post("/v1/authorize")
def authorize(request: ToolCallRequest) -> dict:
    scope = _registry.get(request.agent_id)

    hard_limit = check_hard_limits(request, scope)
    if hard_limit is not None:
        result = hard_limit
    else:
        fast_path = triage.quick_check(request, scope)
        if fast_path == "safe":
            result = ReviewResult(
                decision=Decision.ALLOW,
                rationale="Cleared by Gemma triage — plainly in scope.",
                reviewed_by="gemma-triage",
            )
        else:
            result = review(request, scope)

    token = None
    if result.decision == Decision.ALLOW:
        token = auth_token.sign_token(
            agent_id=request.agent_id, tool=request.tool, decision=result.decision.value
        )

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

    return {
        "decision": result.decision.value,
        "rationale": result.rationale,
        "reviewed_by": result.reviewed_by,
        "token": token,
    }


@app.get("/v1/log")
def log() -> list[dict]:
    return [r.model_dump() for r in _ledger.all()]
