"""The three demo agents Warden governs: search, booking, payment.

Each is deliberately a thin ADK Agent plus one "real" tool — the point of
the demo isn't a sophisticated fleet, it's making Warden's gateway the only
path to actually doing anything. Every tool call goes through
`call_via_warden` first; nothing calls `_TOOLS` directly.
"""

from __future__ import annotations

import httpx

WARDEN_URL = "http://localhost:8080"


def _search_flights(args: dict) -> dict:
    return {"flights": [{"id": "FL42", "price_usd": 310}]}


def _hold_booking(args: dict) -> dict:
    return {"held": True, "hold_id": "HOLD-91"}


def _charge_payment(args: dict) -> dict:
    return {"charged": True, "amount_usd": args.get("amount_usd")}


_TOOLS = {
    "flights.search": _search_flights,
    "flights.hold": _hold_booking,
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
