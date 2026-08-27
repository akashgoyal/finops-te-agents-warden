"""The policy reviewer — Warden's ADK agent, backed by Gemini 3.5 Flash.

Anything Gemma's triage pass didn't wave through lands here. This agent
reads the fleet's plain-language policy doc plus the specific call an agent
is attempting, and returns a structured allow/block/escalate decision with
a rationale that goes straight into the audit ledger.

Built with the ADK Agent/Runner API current as of early 2026. ADK's Runner
surface moves fast — if this breaks on your installed version, the shape to
preserve is: build an Agent with a model + instruction, run one turn with
the call details as the message, and parse the JSON it returns.
"""

from __future__ import annotations

import json
from pathlib import Path

from warden.config import get_settings
from warden.models import AgentScope, Decision, ReviewResult, ToolCallRequest

_POLICY_PATH = Path(__file__).resolve().parent.parent / "demo" / "policy.md"

_INSTRUCTION = """You are Warden, the policy reviewer for a fleet of task agents.
You will be given the fleet's policy document, the calling agent's declared
scope, and one tool call it is attempting. Decide ALLOW, BLOCK, or ESCALATE.

- ALLOW: the call is within scope and the policy doesn't restrict it further.
- BLOCK: the call is outside the agent's declared scope, or the policy
  explicitly forbids it (e.g. a value cap, a missing confirmation flag).
- ESCALATE: the call is ambiguous enough that a human should decide.

Respond with ONLY a JSON object: {"decision": "ALLOW"|"BLOCK"|"ESCALATE", "rationale": "<one sentence, specific to this call>"}
"""


def _load_policy() -> str:
    if _POLICY_PATH.exists():
        return _POLICY_PATH.read_text()
    return "(no policy.md found — see demo/policy.md)"


def review(request: ToolCallRequest, scope: AgentScope | None) -> ReviewResult:
    settings = get_settings()

    if settings.stub_mode:
        return _stub_review(request, scope)

    prompt = (
        f"POLICY:\n{_load_policy()}\n\n"
        f"AGENT SCOPE for '{request.agent_id}': "
        f"{scope.model_dump() if scope else 'UNKNOWN AGENT — not registered'}\n\n"
        f"ATTEMPTED CALL: tool={request.tool!r} args={request.args} "
        f"stated_reason={request.reason!r}"
    )

    reviewer_label = (
        f"ollama-reviewer:{settings.ollama_review_model}"
        if settings.model_backend == "ollama"
        else f"gemini-reviewer:{settings.gemini_model}"
    )

    try:
        decision, rationale = _run_adk_turn(prompt)
    except Exception as exc:  # ADK/model hiccup — fail closed, never fail open
        return ReviewResult(
            decision=Decision.ESCALATE,
            rationale=f"Reviewer error, escalating to a human: {exc}",
            reviewed_by=reviewer_label,
        )

    return ReviewResult(decision=decision, rationale=rationale, reviewed_by=reviewer_label)


def _resolve_model():
    """Same ADK Agent either way — only the model backend changes.

    Local dev (default): Ollama, via ADK's LiteLLM wrapper — no API key,
    no cloud call, no rate limit. Once that's proven out, flip
    MODEL_BACKEND=gemini in .env and nothing else in this file changes.
    """
    settings = get_settings()
    if settings.model_backend == "ollama":
        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(model=f"ollama_chat/{settings.ollama_review_model}", api_base=settings.ollama_host)
    return settings.gemini_model  # ADK accepts a plain Gemini model string directly


def _run_adk_turn(prompt: str) -> tuple[Decision, str]:
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = Agent(
        name="policy_reviewer",
        model=_resolve_model(),
        description="Reviews agent tool calls against Warden's fleet policy.",
        instruction=_INSTRUCTION,
    )
    runner = InMemoryRunner(agent=agent, app_name="warden")
    session = runner.session_service.create_session_sync(app_name="warden", user_id="gateway")

    final_text = ""
    for event in runner.run(
        user_id="gateway",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""

    parsed = json.loads(_extract_json(final_text))
    return Decision(parsed["decision"].lower()), parsed["rationale"]


def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in reviewer output: {text!r}")
    return text[start : end + 1]


def _stub_review(request: ToolCallRequest, scope: AgentScope | None) -> ReviewResult:
    """Deterministic fallback so the fleet demo runs with zero API calls."""
    if scope is None:
        return ReviewResult(
            decision=Decision.BLOCK,
            rationale=f"'{request.agent_id}' is not a registered agent.",
            reviewed_by="stub",
        )
    if request.tool not in scope.allowed_tools:
        return ReviewResult(
            decision=Decision.BLOCK,
            rationale=(
                f"'{request.agent_id}' is scoped to {scope.allowed_tools}, "
                f"not '{request.tool}'."
            ),
            reviewed_by="stub",
        )
    return ReviewResult(decision=Decision.ALLOW, rationale="Within declared scope.", reviewed_by="stub")
