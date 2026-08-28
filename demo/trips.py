"""Trip presets — the pills in the dashboard, and the CLI's input.

Prices vary by route on purpose: SFO → SIN's flight alone crosses the
$2,000 cap, so that route always escalates and pauses right after the
flight payment — it never reaches hotel or cab. The others complete in
full. That's real variation driven by real numbers hitting a real
guardrail, not different scripts per pill.

Every preset has hotel_agent attempt to pay for the room directly, right
after holding it — a genuine scope violation Warden has to catch. That's
not a special "exploit" preset; it's simply how hotel_agent behaves once
it has a total in hand, on every trip. What happens next (retry via
payment_agent, or abort) is decided live by warden/orchestrator_agent.py.
"""

TRIP_PRESETS = {
    "sfo-sin": {"id": "sfo-sin", "label": "SFO → SIN", "origin": "SFO", "dest": "SIN",
                "flight_price": 2450, "hotel_price": 340, "cab_price": 38},
    "nyc-lon": {"id": "nyc-lon", "label": "NYC → LON", "origin": "NYC", "dest": "LON",
                "flight_price": 1780, "hotel_price": 410, "cab_price": 52},
    "sea-tok": {"id": "sea-tok", "label": "SEA → TOK", "origin": "SEA", "dest": "TOK",
                "flight_price": 1590, "hotel_price": 260, "cab_price": 34},
    "aus-chi": {"id": "aus-chi", "label": "AUS → CHI", "origin": "AUS", "dest": "CHI",
                "flight_price": 480, "hotel_price": 195, "cab_price": 28},
}


def build_plan(preset_id: str) -> list[dict]:
    """The ordered call plan for one trip. Built fresh each call."""
    t = TRIP_PRESETS[preset_id]
    dest = t["dest"]
    return [
        {
            "step": "search_flight", "agent_id": "search_agent", "tool": "flights.search",
            "args": {"origin": t["origin"], "dest": dest, "price_usd": t["flight_price"]},
            "reason": "user asked for flights",
            "traveler_copy": f"Searching flights {t['origin']} → {dest}…",
        },
        {
            "step": "hold_flight", "agent_id": "booking_agent", "tool": "flights.hold",
            "args": {"flight_id": "FL42"},
            "reason": "user picked this flight",
            "traveler_copy": "Holding your seat…",
        },
        {
            "step": "pay_flight", "agent_id": "payment_agent", "tool": "payments.charge",
            "args": {"amount_usd": t["flight_price"], "user_confirmed": True},
            "reason": "user confirmed the flight",
            "traveler_copy": f"Charging your card ${t['flight_price']:,} for the flight…",
        },
        {
            "step": "search_hotel", "agent_id": "hotel_agent", "tool": "hotel.search",
            "args": {"city": dest, "price_usd": t["hotel_price"]},
            "reason": "user needs a hotel at the destination",
            "traveler_copy": f"Searching hotels in {dest}…",
        },
        {
            "step": "hold_hotel", "agent_id": "hotel_agent", "tool": "hotel.hold",
            "args": {"hotel_id": "HTL-7"},
            "reason": "user picked this hotel",
            "traveler_copy": "Holding your room…",
        },
        {
            # Built-in scope violation, on every trip — see module docstring.
            "step": "pay_hotel_attempt", "agent_id": "hotel_agent", "tool": "payments.charge",
            "args": {"amount_usd": t["hotel_price"], "user_confirmed": True},
            "reason": "already have the total, charging it now",
            "traveler_copy": f"Hotel agent attempting to charge ${t['hotel_price']:,} directly…",
        },
        {
            "step": "search_cab", "agent_id": "cab_agent", "tool": "cab.search",
            "args": {"city": dest},
            "reason": "user needs ground transport at the destination",
            "traveler_copy": f"Finding a cab in {dest}…",
        },
        {
            "step": "book_cab", "agent_id": "cab_agent", "tool": "cab.book",
            "args": {"cab_id": "CAB-3"},
            "reason": "user confirmed pickup",
            "traveler_copy": "Booking your cab (pay on arrival)…",
        },
    ]
