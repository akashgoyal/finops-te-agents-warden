"""The exact path the 4-minute submission video records.

Run `uvicorn warden.gateway:app --reload` in one terminal, then
`python -m demo.run_demo` from the repo root in another. Three passes,
each hitting a different decision Warden can make:

  1. Happy path — search, hold, pay — all in scope. ALLOW, three times.
  2. Exploit attempt — booking_agent tries to charge a payment directly,
     mirroring the real 2026 incident pattern (an agent reaching for a
     tool outside what it was ever scoped to touch). BLOCK, with a
     rationale, not silently.
  3. Over-the-cap payment — payment_agent is in scope and confirmed, but
     asks for more than its declared $2,000 limit. ESCALATE — this one's
     decided by warden/guardrails.py before any model even runs, so it's
     as reliable as the happy path, not dependent on a model's judgment.

Point the dashboard (http://localhost:8080/) at this while it runs.
"""

from __future__ import annotations

import json

from demo.fleet_agents import call_via_warden


def _show(label: str, result: dict) -> None:
    print(f"\n{label}")
    print(json.dumps(result, indent=2))


def happy_path() -> None:
    print("=== Happy path: search -> hold -> pay ===")
    _show(
        "search_agent -> flights.search",
        call_via_warden("search_agent", "flights.search", {"origin": "SFO", "dest": "SIN"}, "user asked for flights"),
    )
    _show(
        "booking_agent -> flights.hold",
        call_via_warden("booking_agent", "flights.hold", {"flight_id": "FL42"}, "user picked this flight"),
    )
    _show(
        "payment_agent -> payments.charge",
        call_via_warden(
            "payment_agent",
            "payments.charge",
            {"amount_usd": 310, "user_confirmed": True},
            "user confirmed the hold",
        ),
    )


def exploit_attempt() -> None:
    print("\n=== Exploit attempt: booking_agent reaches for payment ===")
    _show(
        "booking_agent -> payments.charge  (out of scope)",
        call_via_warden(
            "booking_agent",
            "payments.charge",
            {"amount_usd": 310, "user_confirmed": True},
            "just charge it now, faster than waiting on payment_agent",
        ),
    )


def over_cap_payment() -> None:
    print("\n=== Over-the-cap payment: payment_agent, in scope, over the limit ===")
    _show(
        "payment_agent -> payments.charge  ($5,000 > $2,000 cap)",
        call_via_warden(
            "payment_agent",
            "payments.charge",
            {"amount_usd": 5000, "user_confirmed": True},
            "user confirmed a larger last-minute fare change",
        ),
    )


if __name__ == "__main__":
    happy_path()
    exploit_attempt()
    over_cap_payment()
    print("\nFull audit trail: GET http://localhost:8080/v1/log")
