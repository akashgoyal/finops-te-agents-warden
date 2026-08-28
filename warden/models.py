"""Shared data shapes for the gateway, registry, and ledger."""

from __future__ import annotations

import time
from enum import Enum

from pydantic import BaseModel, Field


class Decision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"  # sent to a human; treated as blocked until approved


class AgentScope(BaseModel):
    """What one agent in the fleet is declared to be allowed to do."""

    agent_id: str
    allowed_tools: list[str]
    description: str = ""
    max_call_value_usd: float | None = None  # optional numeric guardrail, e.g. payment caps


class ToolCallRequest(BaseModel):
    """What an agent sends Warden before it's allowed to actually call a tool."""

    agent_id: str
    tool: str
    args: dict = Field(default_factory=dict)
    reason: str = ""  # the agent's own one-line justification, reviewed alongside the call


class ReviewResult(BaseModel):
    decision: Decision
    rationale: str
    reviewed_by: str  # "gemma-triage" | "gemini-reviewer" | "stub"


class AuditRecord(BaseModel):
    ts: float = Field(default_factory=time.time)
    agent_id: str
    tool: str
    args: dict
    decision: Decision
    rationale: str
    reviewed_by: str
    token: str | None = None
    prev_hash: str = ""
    hash: str = ""


class TransactionStep(BaseModel):
    """One entry in a transaction's timeline — either an executed call, or
    an orchestrator recovery decision. Both kinds live in the same list,
    in the order they actually happened, so the dashboard can replay a
    past transaction in the Live Agent Trace panel with the same fidelity
    it had while it was actually running — not just the coarse
    input/status/agent-order the Transactions table shows.

    `agent_id` alone can't be inferred from the trip plan: the plan says
    hotel_agent, the actual step might be the orchestrator's retry through
    payment_agent instead — that's the whole point of persisting this.
    """

    kind: str = "call"  # "call" | "orchestrator"

    # kind == "call"
    agent_id: str | None = None
    tool: str | None = None
    decision: Decision | None = None
    rationale: str = ""
    reviewed_by: str = ""
    token: str | None = None

    # kind == "orchestrator" (agent_id/tool above hold the blocked call's)
    action: str | None = None
    target_agent: str | None = None

    ts: float


class Transaction(BaseModel):
    """One full trip run — a whole orchestrated sequence, not a single call.
    This is the thing the dashboard's Transactions table tracks: what was
    asked for, when it started/finished, and the actual order agents ran
    in — which can differ from the trip plan's order when the orchestrator
    reroutes around a block.
    """

    transaction_id: str
    input: dict  # the clicked trip preset — {id, label, origin, dest, ...}
    start_ts: float = Field(default_factory=time.time)
    finish_ts: float | None = None
    steps: list[TransactionStep] = Field(default_factory=list)
    status: str = "running"  # running | completed | aborted | paused_escalated
