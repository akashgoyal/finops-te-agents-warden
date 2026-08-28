"""The five demo agents Warden governs: search, booking, hotel, cab, payment.

Each is deliberately a thin wrapper around one "real" tool — the point of
the demo isn't a sophisticated fleet, it's making Warden's gateway the only
path to actually doing anything. Every tool call goes through
`call_via_warden` first; nothing calls `_TOOLS` directly.
"""

from __future__ import annotations

import httpx

WARDEN_URL = "http://localhost:8080"


def _search_flights(args: dict) -> dict:
    return {"flights": [{"id": "FL42", "price_usd": args.get("price_usd", 310)}]}


def _hold_booking(args: dict) -> dict:
    return {"held": True, "hold_id": "HOLD-91"}


def _search_hotel(args: dict) -> dict:
    return {"hotels": [{"id": "HTL-7", "price_usd": args.get("price_usd", 300)}]}


def _hold_hotel(args: dict) -> dict:
    return {"held": True, "hold_id": "HTLHOLD-14"}


def _search_cab(args: dict) -> dict:
    return {"cabs": [{"id": "CAB-3", "eta_min": 6}]}


def _book_cab(args: dict) -> dict:
    return {"booked": True, "booking_id": "CABBK-52"}


def _charge_payment(args: dict) -> dict:
    return {"charged": True, "amount_usd": args.get("amount_usd")}


_TOOLS = {
    "flights.search": _search_flights,
    "flights.hold": _hold_booking,
    "hotel.search": _search_hotel,
    "hotel.hold": _hold_hotel,
    "cab.search": _search_cab,
    "cab.book": _book_cab,
    "payments.charge": _charge_payment,
}


def call_via_warden(agent_id: str, tool: str, args: dict, reason: str) -> dict:
    """What every fleet agent calls instead of touching a tool directly."""
    resp = httpx.post(
        f"{WARDEN_URL}/v1/authorize",
        json={"agent_id": agent_id, "tool": tool, "args": args, "reason": reason},
        timeout=30,
    )
    resp.raise_for_status()
    decision = resp.json()

    if decision["decision"] != "allow":
        return {"executed": False, **decision}

    result = _TOOLS[tool](args)
    return {"executed": True, **decision, "result": result}
