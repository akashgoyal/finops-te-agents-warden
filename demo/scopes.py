"""The demo fleet's declared scopes — the machine-readable half of policy.md.

Shared by the gateway's local auto-seed (so `run_demo.py` works right after
`uvicorn warden.gateway:app`) and `scripts/seed_registry.py` (which writes
the same scopes to Firestore once you're pointed at a real GCP project).
"""

from warden.models import AgentScope

DEMO_SCOPES: list[AgentScope] = [
    AgentScope(
        agent_id="search_agent",
        allowed_tools=["flights.search"],
        description="Finds flight options. Read-only.",
    ),
    AgentScope(
        agent_id="booking_agent",
        allowed_tools=["flights.search", "flights.hold"],
        description="Holds a flight once search picks one. No payment access.",
    ),
    AgentScope(
        agent_id="payment_agent",
        allowed_tools=["payments.charge"],
        description="Only agent allowed to move money.",
        max_call_value_usd=2000,
    ),
]
