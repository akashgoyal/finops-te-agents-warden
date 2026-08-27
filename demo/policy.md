# Fleet policy — travel-booking demo

Three agents work one task: find a flight, hold it, and pay for it.

## search_agent
- May call: `flights.search`
- May not call anything that touches money or writes a booking.

## booking_agent
- May call: `flights.search`, `flights.hold`
- May **not** call `payments.charge` — even if the booking agent decides
  a payment is "obviously fine," charging is out of its declared scope.
  This is the boundary the demo's exploit attempt crosses.

## payment_agent
- May call: `payments.charge`
- Only when `user_confirmed: true` is present in the call args.
- Capped at $2,000 per call — anything above that escalates to a human,
  regardless of confirmation status.

## General rules
- Any agent not listed above is unregistered and every call from it blocks.
- A call to a tool outside an agent's `allowed_tools` blocks, no exceptions —
  scope is enforced even if the reasoning behind the call sounds legitimate.
