"""CLI runner for the demo — same orchestrated trip the dashboard's pills
trigger, just called over HTTP instead of in-process, and printed instead
of streamed.

Run `uvicorn warden.gateway:app --reload` in one terminal, then
`python -m demo.run_demo [preset_id]` from the repo root in another
(default: sfo-sin — the one that escalates). Or skip this entirely and
click a trip pill in the dashboard at http://localhost:8080/ — same
orchestrator, same policy, but streamed live stage-by-stage with a
traveler-facing view alongside it.
"""

from __future__ import annotations

import sys

from demo.fleet_agents import call_via_warden
from demo.trips import TRIP_PRESETS, build_plan


def run(preset_id: str) -> None:
    if preset_id not in TRIP_PRESETS:
        print(f"Unknown preset {preset_id!r}. Choose one of: {', '.join(TRIP_PRESETS)}")
        raise SystemExit(1)

    print(f"=== Trip: {TRIP_PRESETS[preset_id]['label']} ===")
    for step in build_plan(preset_id):
        result = call_via_warden(step["agent_id"], step["tool"], step["args"], step["reason"])
        print(f"\n{step['step']}  ({step['agent_id']} -> {step['tool']})  decision={result['decision']}")
        if result["decision"] != "allow":
            print(f"  rationale: {result['rationale']}")
            if result["decision"] == "escalate":
                print("  (escalated — the CLI doesn't run the orchestrator; see the dashboard for that)")
                break

    print("\nFull audit trail: GET http://localhost:8080/v1/log")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "sfo-sin")
