"""The demo fleet's declared scopes — the machine-readable half of policy.md.

Shared by the gateway's local auto-seed (so `run_demo.py` works right after
`uvicorn warden.gateway:app`) and `scripts/seed_registry.py` (which writes
the same scopes to Firestore once you're pointed at a real GCP project).

Three verticals — flights, hotel, cab — one payment gate. Every vertical
agent can search and hold/book its own thing; none of them can charge a
card. That's deliberate: it's what makes hotel_agent's payment attempt in
demo/trips.py a real scope violation Warden actually has to catch, not a
scripted one.
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
        agent_id="hotel_agent",
        allowed_tools=["hotel.search", "hotel.hold"],
        description="Finds and holds a hotel room at the destination. No payment access.",
    ),
    AgentScope(
        agent_id="cab_agent",
        allowed_tools=["cab.search", "cab.book"],
        description="Books ground transport at the destination. No payment access.",
    ),
    AgentScope(
        agent_id="payment_agent",
        allowed_tools=["payments.charge"],
        description="Only agent allowed to move money, across every vertical.",
        max_call_value_usd=2000,
    ),
]
