"""Stub-mode only — no model calls, no network. Proves the orchestrator's
retry-on-block and pause-on-escalate branching actually fires, not just
that the happy path works.
"""

import os

os.environ.setdefault("WARDEN_STUB_MODE", "true")

from warden.gateway import _registry  # noqa: E402 — seeds the demo scopes on import
from warden.orchestrator import run_trip  # noqa: E402
from warden.orchestrator_agent import decide_recovery  # noqa: E402
from warden.models import ToolCallRequest  # noqa: E402


def test_registry_has_five_agents():
    assert {s.agent_id for s in _registry.all()} == {
        "search_agent", "booking_agent", "hotel_agent", "cab_agent", "payment_agent",
    }


def test_decide_recovery_finds_the_only_valid_candidate():
    blocked = ToolCallRequest(agent_id="hotel_agent", tool="payments.charge", args={"amount_usd": 300})
    recovery = decide_recovery(blocked=blocked, block_rationale="out of scope", candidates=["payment_agent"])
    assert recovery["action"] == "retry"
    assert recovery["target_agent"] == "payment_agent"


def test_decide_recovery_aborts_with_no_candidates():
    blocked = ToolCallRequest(agent_id="ghost_agent", tool="nonexistent.tool", args={})
    recovery = decide_recovery(blocked=blocked, block_rationale="unregistered", candidates=[])
    assert recovery["action"] == "abort"
    assert recovery["target_agent"] is None


def test_cheap_route_completes_with_orchestrator_retry():
    # aus-chi never crosses the payment cap, so this should run the full
    # 8-step plan, hit the built-in hotel_agent payment block once, retry
    # it via payment_agent, and finish 'completed' — not paused or aborted.
    txn = run_trip("aus-chi")
    assert txn.status == "completed"
    agent_order = [s.agent_id for s in txn.steps]
    assert agent_order.count("payment_agent") == 2  # flight charge + the retried hotel charge
    assert "hotel_agent" in agent_order  # the blocked attempt is still a real, logged step


def test_expensive_route_escalates_and_stops_early():
    # sfo-sin's flight alone crosses the $2,000 cap — the trip should
    # escalate right after the flight payment and never reach hotel/cab.
    txn = run_trip("sfo-sin")
    assert txn.status == "paused_escalated"
    agent_order = [s.agent_id for s in txn.steps]
    assert "hotel_agent" not in agent_order
    assert "cab_agent" not in agent_order
