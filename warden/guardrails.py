"""Deterministic, code-enforced limits — checked before any model runs.

Not everything Warden enforces should depend on an LLM getting it right.
A numeric cap like "no single payment over $2,000 without a human" is a
hard rule, not a judgment call — so it's plain Python, not a prompt. This
also means it costs nothing and never varies between runs, unlike triage
or review. Reserve the model calls for the genuinely ambiguous cases;
resolve the unambiguous ones here first.
"""

from __future__ import annotations

from warden.models import AgentScope, Decision, ReviewResult, ToolCallRequest


def check_hard_limits(request: ToolCallRequest, scope: AgentScope | None) -> ReviewResult | None:
    """Returns a ReviewResult if a hard limit fires, else None to fall
    through to triage/review as normal."""

    if scope is None or scope.max_call_value_usd is None:
        return None

    value = request.args.get("amount_usd")
    if not isinstance(value, (int, float)):
        return None

    if value > scope.max_call_value_usd:
        return ReviewResult(
            decision=Decision.ESCALATE,
            rationale=(
                f"${value:,.2f} exceeds {request.agent_id}'s ${scope.max_call_value_usd:,.2f} "
                f"cap — requires human approval regardless of confirmation status."
            ),
            reviewed_by="hard-limit-guardrail",
        )

    return None
