"""CLI runner for the demo — same five scenarios the dashboard's Run
button triggers (demo/scenarios.py), just called over HTTP instead of
in-process, and printed instead of streamed.

Run `uvicorn warden.gateway:app --reload` in one terminal, then
`python -m demo.run_demo` from the repo root in another. Or skip this
entirely and click Run in the dashboard at http://localhost:8080/ — same
five calls, same policy, but streamed live stage-by-stage instead of
printed as a final JSON blob per call.
"""

from __future__ import annotations

import json

from demo.fleet_agents import call_via_warden
from demo.scenarios import SCENARIOS


def _show(step: dict, result: dict) -> None:
    print(f"\n{step['label']}  ({step['agent_id']} -> {step['tool']})")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    for step in SCENARIOS:
        result = call_via_warden(step["agent_id"], step["tool"], step["args"], step["reason"])
        _show(step, result)
    print("\nFull audit trail: GET http://localhost:8080/v1/log")
