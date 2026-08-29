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
import time
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

    reviewer_label = {
        "ollama": f"ollama-reviewer:{settings.ollama_review_model}",
        "vertex": f"vertex-reviewer:{settings.vertex_gemini_model}",
    }.get(settings.model_backend, f"gemini-reviewer:{settings.gemini_model}")

    # Four retries beyond the first attempt, with backoff: a live cloud run
    # surfaced Gemini returning a bare 504 DEADLINE_EXCEEDED on this exact
    # call — not a payload-size issue (the whole prompt is ~2KB), and not
    # purely a thinking-mode issue either (thinking_config on the agent
    # already disables that; disabling it improved but didn't eliminate
    # this — a run with it disabled still hit 504 on 2/3 attempts,
    # consistent with free-tier API rate limiting/latency under the call
    # volume this session generated, not a per-call fluke). Retrying with
    # backoff gives the API room to recover; if every attempt fails we
    # still fail closed to ESCALATE exactly as before.
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            decision, rationale = _run_adk_turn(prompt)
            return ReviewResult(decision=decision, rationale=rationale, reviewed_by=reviewer_label)
        except Exception as exc:  # ADK/model hiccup — retry, then fail closed
            last_exc = exc
            if attempt < 4:
                time.sleep(2 * (attempt + 1))

    return ReviewResult(
        decision=Decision.ESCALATE,
        rationale=f"Reviewer error, escalating to a human: {last_exc}",
        reviewed_by=reviewer_label,
    )


def _resolve_model():
    """Same ADK Agent either way — only the model backend changes.

    Local dev (default): Ollama, via ADK's LiteLLM wrapper — no API key,
    no cloud call, no rate limit. Once that's proven out, flip
    MODEL_BACKEND=gemini in .env and nothing else in this file changes.
    MODEL_BACKEND=vertex is the same Gemini model, just authenticated
    against Vertex AI (ADC, not an API key) instead of the Gemini
    Developer API — the only path Model Armor screening can attach to.
    """
    settings = get_settings()
    if settings.model_backend == "ollama":
        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(model=f"ollama_chat/{settings.ollama_review_model}", api_base=settings.ollama_host)
    if settings.model_backend == "vertex":
        return _timeout_bound_gemini_cls(vertex=True)(model=settings.vertex_gemini_model)
    return _timeout_bound_gemini_cls()(model=settings.gemini_model)


def _timeout_bound_gemini_cls(vertex: bool = False):
    """A Gemini model wrapper that actually times out.

    ADK's own Gemini class builds its api_client as
    Client(http_options=types.HttpOptions(headers=...)) — timeout left at
    the genai SDK default of None. Verified live, not assumed: a real trip
    hung for 2+ minutes with the gateway process idle (0.1% CPU) and no
    error, because the underlying HTTP call to Gemini had nothing bounding
    it. Warden fails closed everywhere else (guardrails, review errors);
    an unbounded network call silently breaking that guarantee is the same
    class of bug. Subclassing just to override api_client with a timeout.

    vertex=True additionally switches the client to Vertex AI mode
    (project + location, ADC auth) instead of the Gemini Developer API
    (api_key auth) — required for Model Armor, which only integrates with
    Vertex AI's generateContent, not the AI Studio endpoint.
    """
    from functools import cached_property

    from google.adk.models.google_llm import Gemini
    from google.genai import Client, types

    class _TimeoutBoundGemini(Gemini):
        # Must stay a cached_property, same as ADK's original: a plain
        # @property rebuilds the Client (and its aiohttp session) on every
        # access, and ADK's Runner drives this from a fresh event loop in a
        # dedicated thread — a churned client/session crossing that boundary
        # surfaced as `AssertionError: self._connector is not None` deep in
        # aiohttp on a live run. Caching once, like upstream does, fixed it.
        @cached_property
        def api_client(self) -> Client:
            kwargs: dict = {
                "http_options": types.HttpOptions(
                    headers=self._tracking_headers,
                    timeout=30_000,  # ms — fail closed instead of hanging the trip
                )
            }
            if vertex:
                settings = get_settings()
                kwargs.update(
                    vertexai=True,
                    project=settings.google_cloud_project,
                    location=settings.vertex_location,
                )
            return Client(**kwargs)

    return _TimeoutBoundGemini


def _generate_content_config():
    """Model Armor prompt/response screening — opt-in, Vertex AI only.

    Returns None (i.e. "no special config") unless MODEL_BACKEND=vertex
    AND both template resource names are set — so the ollama and gemini
    (AI Studio, free tier) paths are completely unaffected either way.

    ADK's Agent rejects a handful of specific fields on generate_content_
    config outright via a pydantic validator (thinking_config, tools,
    system_instruction, response_schema — see the planner comment in
    _run_adk_turn below, and llm_agent.py's own validator). model_armor_
    config isn't one of them — checked against the installed ADK version
    before relying on this, not assumed.
    """
    settings = get_settings()
    if settings.model_backend != "vertex":
        return None
    if not (settings.model_armor_prompt_template and settings.model_armor_response_template):
        return None

    from google.genai import types

    return types.GenerateContentConfig(
        model_armor_config=types.ModelArmorConfig(
            prompt_template_name=settings.model_armor_prompt_template,
            response_template_name=settings.model_armor_response_template,
        )
    )


def _run_adk_turn(prompt: str) -> tuple[Decision, str]:
    from google.adk.agents import Agent
    from google.adk.planners import BuiltInPlanner
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = Agent(
        name="policy_reviewer",
        model=_resolve_model(),
        description="Reviews agent tool calls against Warden's fleet policy.",
        instruction=_INSTRUCTION,
        # thinking_budget=0 disables extended "thinking" entirely. Verified
        # live: this ALLOW/BLOCK/ESCALATE call from a ~2KB prompt hit a real
        # 504 DEADLINE_EXCEEDED from Gemini's own server 6/6 times across
        # two full trip runs on Cloud Run (and once locally) — the model
        # spending too long in thinking mode on what's really a small
        # structured judgment call, hitting its own server-side deadline.
        # This is a classification decision, not something that benefits
        # from open-ended reasoning. ADK requires this go through
        # LlmAgent.planner, not generate_content_config directly (that
        # raises a pydantic validation error).
        planner=BuiltInPlanner(thinking_config=types.ThinkingConfig(thinking_budget=0)),
        generate_content_config=_generate_content_config(),
    )
    runner = InMemoryRunner(agent=agent, app_name="warden")
    session = runner.session_service.create_session_sync(app_name="warden", user_id="gateway")

    final_text = ""
    for event in runner.run(
        user_id="gateway",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        # Not gated on is_final_response(), and not just parts[0]: Gemini's
        # thinking-mode responses can split across multiple parts on an
        # event that doesn't get marked "final", and grabbing only the
        # first part silently returned a thought-signature part with no
        # text on it in production — a real empty-response bug found by
        # actually running this against the cloud backend, not assumed.
        # Track the last non-empty text seen across every part of every
        # event instead; far more robust to whatever shape a given model
        # or ADK version produces.
        if event.content and event.content.parts:
            text = "".join(p.text for p in event.content.parts if getattr(p, "text", None))
            if text.strip():
                final_text = text

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
