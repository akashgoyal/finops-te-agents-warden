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
    """One executed call within a transaction — including orchestrator-
    injected retries, which is why `agent_id` alone can't be inferred from
    the trip plan: the plan says hotel_agent, the actual step might be the
    orchestrator's retry through payment_agent instead."""

    agent_id: str
    tool: str
    decision: Decision
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
