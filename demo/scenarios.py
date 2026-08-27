"""The demo's five calls, defined once.

Used by demo/run_demo.py (CLI, calls through HTTP like a real fleet agent
would) and warden/gateway.py's POST /v1/demo/run (triggered from the
dashboard's Run button, calls in-process so it can publish live events at
each stage). One definition, two ways to trigger it — not two demos that
can drift apart.

`traveler_copy` is what the mocked traveler-facing app shows — plain
consumer language, not agent/tool names.
"""

SCENARIOS = [
    {
        "label": "Search flights",
        "agent_id": "search_agent",
        "tool": "flights.search",
        "args": {"origin": "SFO", "dest": "SIN"},
        "reason": "user asked for flights",
        "traveler_copy": "Searching flights SFO → SIN…",
    },
    {
        "label": "Hold the flight",
        "agent_id": "booking_agent",
        "tool": "flights.hold",
        "args": {"flight_id": "FL42"},
        "reason": "user picked this flight",
        "traveler_copy": "Holding your seat on FL42…",
    },
    {
        "label": "Charge the card",
        "agent_id": "payment_agent",
        "tool": "payments.charge",
        "args": {"amount_usd": 310, "user_confirmed": True},
        "reason": "user confirmed the hold",
        "traveler_copy": "Charging your card $310…",
    },
    {
        "label": "Exploit attempt: booking agent reaches for payment",
        "agent_id": "booking_agent",
        "tool": "payments.charge",
        "args": {"amount_usd": 310, "user_confirmed": True},
        "reason": "just charge it now, faster than waiting on payment_agent",
        "traveler_copy": "Booking agent tried to charge your card directly…",
    },
    {
        "label": "Over the cap: payment agent asks for $5,000",
        "agent_id": "payment_agent",
        "tool": "payments.charge",
        "args": {"amount_usd": 5000, "user_confirmed": True},
        "reason": "user confirmed a larger last-minute fare change",
        "traveler_copy": "Requesting approval for a $5,000 charge…",
    },
]
