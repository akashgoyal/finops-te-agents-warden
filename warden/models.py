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
