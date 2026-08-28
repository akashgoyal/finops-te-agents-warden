"""Runs one trip end-to-end: executes demo/trips.py's plan in order, and
when a call blocks, asks warden/orchestrator_agent.py what to do next
instead of just stopping.

This is what makes agent execution order genuinely variable rather than a
fixed script: a clean route runs eight allowed calls straight through; a
route whose flight crosses the payment cap escalates and stops after
three; every route has hotel_agent's payment attempt blocked and rerouted
through payment_agent by a live decision, not a scripted retry. See
demo/trips.py's docstring for the concrete numbers behind each case.
"""

from __future__ import annotations

import time

from warden import events
from warden.models import Decision, Transaction, TransactionStep, ToolCallRequest
from warden.orchestrator_agent import decide_recovery

_STEP_PACING_SECONDS = 0.35  # lets the UI render each stage instead of flashing by


def run_trip(preset_id: str) -> Transaction:
    from demo.trips import TRIP_PRESETS, build_plan
    from warden.gateway import _process_call, _registry
    from warden.transactions import get_store

    preset = TRIP_PRESETS[preset_id]
    plan = build_plan(preset_id)
    store = get_store()

    txn = Transaction(transaction_id=events.new_call_id(), input=preset)
    store.start(txn)
    events.publish({
        "type": "transaction_started", "transaction_id": txn.transaction_id,
        "input": preset, "start_ts": txn.start_ts,
    })

    aborted = False
    paused = False
    i = 0

    while i < len(plan):
        step = plan[i]
        request = ToolCallRequest(
            agent_id=step["agent_id"], tool=step["tool"],
            args=step["args"], reason=step["reason"],
        )
        result = _process_call(
            request, label=step["step"], traveler_copy=step.get("traveler_copy"),
            transaction_id=txn.transaction_id,
        )
        txn.steps.append(TransactionStep(
            agent_id=step["agent_id"], tool=step["tool"], args=step["args"],
            decision=Decision(result["decision"]),
            rationale=result["rationale"], reviewed_by=result["reviewed_by"],
            token=result.get("token"), ts=time.time(),
        ))

        if result["decision"] == "allow":
            i += 1
            time.sleep(_STEP_PACING_SECONDS)
            continue

        if result["decision"] == "escalate":
            # Deterministic on purpose — an over-cap charge needs a human,
            # not a model's opinion. Nothing left in the plan runs.
            paused = True
            break

        # decision == block -> a scope violation. Ask the orchestrator
        # whether the agent actually scoped for this tool should retry it.
        candidates = [
            s.agent_id for s in _registry.all()
            if step["tool"] in s.allowed_tools and s.agent_id != step["agent_id"]
        ]
        recovery = decide_recovery(blocked=request, block_rationale=result["rationale"], candidates=candidates)
        events.publish({
            "type": "orchestrator_decision", "transaction_id": txn.transaction_id,
            "action": recovery["action"], "target_agent": recovery["target_agent"],
            "rationale": recovery["rationale"], "decided_by": recovery["decided_by"],
            "blocked_agent": step["agent_id"], "tool": step["tool"],
        })
        txn.steps.append(TransactionStep(
            kind="orchestrator", agent_id=step["agent_id"], tool=step["tool"], args=step["args"],
            action=recovery["action"], target_agent=recovery["target_agent"],
            rationale=recovery["rationale"], reviewed_by=recovery["decided_by"],
            ts=time.time(),
        ))

        if recovery["action"] == "abort":
            aborted = True
            break

        retry_request = ToolCallRequest(
            agent_id=recovery["target_agent"], tool=step["tool"], args=step["args"],
            reason=f"orchestrator retry after {step['agent_id']} was blocked",
        )
        retry_result = _process_call(
            retry_request, label=f"retry: {step['step']}",
            traveler_copy=f"Retrying via {recovery['target_agent']}…",
            transaction_id=txn.transaction_id,
        )
        txn.steps.append(TransactionStep(
            agent_id=recovery["target_agent"], tool=step["tool"], args=step["args"],
            decision=Decision(retry_result["decision"]),
            rationale=retry_result["rationale"], reviewed_by=retry_result["reviewed_by"],
            token=retry_result.get("token"), ts=time.time(),
        ))
        i += 1
        time.sleep(_STEP_PACING_SECONDS)

    txn.finish_ts = time.time()
    txn.status = "aborted" if aborted else "paused_escalated" if paused else "completed"
    events.publish({
        "type": "transaction_finished", "transaction_id": txn.transaction_id,
        "finish_ts": txn.finish_ts, "status": txn.status,
        "agent_order": [s.agent_id for s in txn.steps],
    })
    return txn
