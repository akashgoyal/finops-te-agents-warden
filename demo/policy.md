# Fleet policy — corporate Travel & Expense (T&E)

Five agents cover one trip: flights, hotel, ground transport, and one
shared gate for payment. This is a policy a Finance Ops team already
has a written version of.

## search_agent
- May call: `flights.search`
- Read-only. May not hold, book, or pay for anything.

## booking_agent
- May call: `flights.search`, `flights.hold`
- May **not** call `payments.charge` — holding a flight is not the same
  as paying for it, even if the booking agent decides a payment is
  "obviously fine." Charging is out of its declared scope, no exceptions.

## hotel_agent
- May call: `hotel.search`, `hotel.hold`
- May **not** call `payments.charge` — same boundary as booking_agent,
  same reasoning. Holding a room isn't authorization to pay for it.

## cab_agent
- May call: `cab.search`, `cab.book`
- Ground transport is pay-on-arrival in this policy — cab_agent never
  needs payment access at all.

## payment_agent
- May call: `payments.charge`
- Only when `user_confirmed: true` is present in the call args.
- Capped at $2,000 per call — anything above that escalates to a human,
  regardless of confirmation status. This applies per charge, not per
  trip: a $2,400 flight escalates even if the hotel and cab stay well
  under the cap.

## General rules
- Any agent not listed above is unregistered and every call from it blocks.
- A call to a tool outside an agent's `allowed_tools` blocks, no
  exceptions — scope is enforced even if the reasoning behind the call
  sounds legitimate ("I already have the total, I'll just charge it").
- When a call blocks because of a scope violation, the fleet's
  orchestrator (`warden/orchestrator_agent.py`) decides whether to retry
  the same action through the agent that's actually scoped for it, or
  abort the trip — see the "Live agent trace" panel for that decision
  live, not just the retry itself.
