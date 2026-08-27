"""In-process pub/sub for live dashboard events.

Every stage of every call — not just the final decision — gets published
here: intercept, guardrail check, triage, review, decision, ledger write.
The dashboard subscribes over SSE (`GET /v1/events`) and renders each stage
as it happens, instead of polling the ledger and reconstructing history
after the fact.

Plain `queue.Queue`, not asyncio — `warden/gateway.py`'s call-processing
runs as sync code (in FastAPI's threadpool), so publishing has to be safe
to call from a thread. The SSE endpoint bridges back to async with
`run_in_threadpool`.
"""

from __future__ import annotations

import queue as pyqueue
import time
import uuid

_subscribers: list[pyqueue.Queue] = []


def subscribe() -> pyqueue.Queue:
    q: pyqueue.Queue = pyqueue.Queue()
    _subscribers.append(q)
    return q


def unsubscribe(q: pyqueue.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)


def publish(event: dict) -> None:
    event.setdefault("ts", time.time())
    for q in list(_subscribers):
        q.put(event)


def new_call_id() -> str:
    return uuid.uuid4().hex[:10]
