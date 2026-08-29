"""The orchestrator — decides what happens after a blocked call.

Not every block is game over. hotel_agent tries to pay for a room and
gets blocked because it was never scoped for that — the reasonable fix is
usually "retry the same action through the agent that's actually allowed
to do it." This agent decides that.

Deliberately constrained: the candidate agent(s) are found the same way
warden/guardrails.py finds hard limits — deterministically, by looking up
the registry for who's actually scoped for the blocked tool. The LLM
doesn't invent a target agent from scratch; it only confirms whether
retrying through a real candidate is reasonable, or the trip should abort.
That keeps a flaky small local model from routing a payment to something
it shouldn't, while still making a genuine judgment call, not a scripted
one — same trust-but-verify pattern as everywhere else in Warden.

Same ADK Agent + backend-swap as warden/reviewer_agent.py, reusing its
model-resolution logic directly rather than duplicating it.
"""

from __future__ import annotations

import json

from warden.config import get_settings
from warden.models import ToolCallRequest
from warden.reviewer_agent import _extract_json, _generate_content_config, _resolve_model

_INSTRUCTION = """You are the orchestrator for a corporate Travel & Expense agent
fleet. A call was just blocked because the calling agent wasn't scoped for
that tool. You're given the blocked call, why it blocked, and the agent(s) in
the fleet that ARE scoped for that exact tool. Decide whether retrying the
same action through one of those candidates is reasonable, or whether the
trip should abort instead (e.g. the original request itself looks wrong, not
just misrouted).

Respond with ONLY a JSON object:
{"action": "retry"|"abort", "target_agent": "<one of the candidates, or null if abort>", "rationale": "<one sentence>"}
"""


def decide_recovery(*, blocked: ToolCallRequest, block_rationale: str, candidates: list[str]) -> dict:
    """Returns {"action", "target_agent", "rationale", "decided_by"}."""
    settings = get_settings()

    if not candidates:
        return {
            "action": "abort",
            "target_agent": None,
            "rationale": f"No agent in the fleet is scoped for '{blocked.tool}' — nothing to retry through.",
            "decided_by": "orchestrator-fallback",
        }

    if settings.stub_mode:
        return _stub_decide(blocked, candidates)

    prompt = (
        f"BLOCKED CALL: agent={blocked.agent_id!r} tool={blocked.tool!r} "
        f"args={blocked.args} reason={blocked.reason!r}\n"
        f"WHY IT BLOCKED: {block_rationale}\n"
        f"CANDIDATE AGENTS (scoped for {blocked.tool!r}): {candidates}"
    )

    try:
        decision = _run_adk_turn(prompt)
    except Exception as exc:
        # Model hiccup — retry via the already-validated candidate rather
        # than aborting a whole trip over a transient error. We know the
        # candidate is structurally correct; only the judgment was skipped.
        return {
            "action": "retry",
            "target_agent": candidates[0],
            "rationale": f"Orchestrator model error ({exc}); retrying via the scoped candidate.",
            "decided_by": "orchestrator-fallback",
        }

    action = decision.get("action")
    target = decision.get("target_agent")
    if action not in ("retry", "abort"):
        action = "retry"
    if action == "retry" and target not in candidates:
        target = candidates[0]  # never trust an invented target — constrain to what's real

    model_label = {
        "ollama": settings.ollama_review_model,
        "vertex": settings.vertex_gemini_model,
    }.get(settings.model_backend, settings.gemini_model)
    backend_prefix = "vertex-orchestrator-agent" if settings.model_backend == "vertex" else "orchestrator-agent"
    return {
        "action": action,
        "target_agent": target if action == "retry" else None,
        "rationale": decision.get("rationale", ""),
        "decided_by": f"{backend_prefix}:{model_label}",
    }


def _run_adk_turn(prompt: str) -> dict:
    from google.adk.agents import Agent
    from google.adk.planners import BuiltInPlanner
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = Agent(
        name="orchestrator",
        model=_resolve_model(),
        description="Decides retry-vs-abort after a blocked fleet call.",
        instruction=_INSTRUCTION,
        # See the matching comment in reviewer_agent.py — disabling
        # thinking avoids the same server-side 504 DEADLINE_EXCEEDED
        # this call is just as susceptible to (same model, same class
        # of small structured judgment call). Goes through
        # LlmAgent.planner, not generate_content_config directly (ADK
        # raises a pydantic validation error otherwise).
        planner=BuiltInPlanner(thinking_config=types.ThinkingConfig(thinking_budget=0)),
        generate_content_config=_generate_content_config(),
    )
    runner = InMemoryRunner(agent=agent, app_name="warden")
    session = runner.session_service.create_session_sync(app_name="warden", user_id="orchestrator")

    final_text = ""
    for event in runner.run(
        user_id="orchestrator",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        # See the matching comment in reviewer_agent.py — a live run against
        # the Gemini backend hit an event whose first part had no text
        # (thinking-mode artifact), so this isn't gated on is_final_response()
        # or parts[0] alone; it tracks the last non-empty joined text across
        # every part of every event instead.
        if event.content and event.content.parts:
            text = "".join(p.text for p in event.content.parts if getattr(p, "text", None))
            if text.strip():
                final_text = text

    return json.loads(_extract_json(final_text))


def _stub_decide(blocked: ToolCallRequest, candidates: list[str]) -> dict:
    return {
        "action": "retry",
        "target_agent": candidates[0],
        "rationale": f"Stub: retrying via {candidates[0]}, the only agent scoped for '{blocked.tool}'.",
        "decided_by": "stub",
    }
