"""Fast, free first-pass filter using Gemma.

Most tool calls a fleet makes are obviously within scope — no need to spend
a Gemini call reasoning about them. Gemma checks the call against the
agent's declared tool list in one cheap pass:
  - clearly in-scope and low-risk -> ALLOW immediately (no escalation)
  - anything else -> escalate to the Gemini reviewer for real policy reasoning

This is the cost-optimization half of Warden's architecture story, not a
bonus-points afterthought: it's the reason most calls never touch a paid
model at all.
"""

from __future__ import annotations

from warden.config import get_settings
from warden.models import AgentScope, ToolCallRequest

_TRIAGE_PROMPT = """You are a fast pre-filter for an agent-action gateway.
Given the agent's allowed tools and the tool call it just attempted, answer
with exactly one word: SAFE if the tool is plainly in the allowed list and
the args look like a normal, unremarkable use of it. Otherwise answer REVIEW.

Allowed tools: {allowed_tools}
Called tool: {tool}
Args: {args}
Answer:"""


def quick_check(request: ToolCallRequest, scope: AgentScope | None) -> str:
    """Returns "safe" or "review"."""
    settings = get_settings()

    if scope is None:
        return "review"  # unknown agent — never fast-path an agent we have no record of

    if request.tool not in scope.allowed_tools:
        return "review"  # let the full reviewer write the rationale for a block

    if settings.stub_mode:
        return _stub_quick_check(request, scope)

    from google import genai

    client = genai.Client(api_key=settings.google_api_key)
    prompt = _TRIAGE_PROMPT.format(
        allowed_tools=", ".join(scope.allowed_tools),
        tool=request.tool,
        args=request.args,
    )
    response = client.models.generate_content(model=settings.gemma_model, contents=prompt)
    text = (response.text or "").strip().upper()
    return "safe" if text.startswith("SAFE") else "review"


def _stub_quick_check(request: ToolCallRequest, scope: AgentScope) -> str:
    """Deterministic stand-in so the demo runs before any API key is wired up."""
    if scope.max_call_value_usd is not None:
        value = request.args.get("amount_usd")
        if isinstance(value, (int, float)) and value > scope.max_call_value_usd:
            return "review"
    return "safe"
