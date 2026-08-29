"""Runs entirely in stub mode — no API key, no GCP, no network calls.
This is the test to run before you ever touch a cloud credential.
"""

import os

os.environ.setdefault("WARDEN_STUB_MODE", "true")

from fastapi.testclient import TestClient

from warden.gateway import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_in_scope_call_is_allowed():
    resp = client.post(
        "/v1/authorize",
        json={"agent_id": "search_agent", "tool": "flights.search", "args": {}, "reason": "test"},
    )
    body = resp.json()
    assert body["decision"] == "allow"
    assert body["token"] is not None


def test_out_of_scope_call_is_blocked():
    resp = client.post(
        "/v1/authorize",
        json={
            "agent_id": "booking_agent",
            "tool": "payments.charge",
            "args": {"amount_usd": 310, "user_confirmed": True},
            "reason": "exploit attempt",
        },
    )
    body = resp.json()
    assert body["decision"] == "block"
    assert body["token"] is None


def test_over_cap_payment_escalates_without_calling_a_model():
    # payment_agent is in scope and would pass triage — this only blocks
    # because of warden/guardrails.py's deterministic check, which runs
    # before triage/review and doesn't depend on stub mode being on.
    resp = client.post(
        "/v1/authorize",
        json={
            "agent_id": "payment_agent",
            "tool": "payments.charge",
            "args": {"amount_usd": 5000, "user_confirmed": True},
            "reason": "test",
        },
    )
    body = resp.json()
    assert body["decision"] == "escalate"
    assert body["reviewed_by"] == "hard-limit-guardrail"
    assert body["token"] is None


def test_within_cap_payment_is_unaffected_by_the_guardrail():
    resp = client.post(
        "/v1/authorize",
        json={
            "agent_id": "payment_agent",
            "tool": "payments.charge",
            "args": {"amount_usd": 500, "user_confirmed": True},
            "reason": "test",
        },
    )
    assert resp.json()["decision"] == "allow"


def test_unregistered_agent_is_blocked():
    resp = client.post(
        "/v1/authorize",
        json={"agent_id": "ghost_agent", "tool": "flights.search", "args": {}, "reason": "test"},
    )
    assert resp.json()["decision"] == "block"


def test_log_grows_with_each_call():
    before = len(client.get("/v1/log").json())
    client.post(
        "/v1/authorize",
        json={"agent_id": "search_agent", "tool": "flights.search", "args": {}, "reason": "test"},
    )
    after = len(client.get("/v1/log").json())
    assert after == before + 1
