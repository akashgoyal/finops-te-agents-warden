"""Signed, task-bounded authorization tokens.

Not a full OAuth/JWT stack on purpose — this is a hackathon-scale stand-in
for what Google's Agent Identity / Agent Payments Protocol work is pushing
toward: a token that names exactly one agent, one action, and one decision,
signed so it can't be forged or replayed for a different call.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

from warden.config import get_settings


def sign_token(*, agent_id: str, tool: str, decision: str) -> str:
    settings = get_settings()
    payload = {
        "agent_id": agent_id,
        "tool": tool,
        "decision": decision,
        "nonce": uuid.uuid4().hex,
        "iat": int(time.time()),
    }
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    sig = hmac.new(settings.warden_secret_key.encode("utf-8"), body, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(body).decode() + "." + base64.urlsafe_b64encode(sig).decode()
    return token


def verify_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        body_b64, sig_b64 = token.split(".")
        body = base64.urlsafe_b64decode(body_b64)
        sig = base64.urlsafe_b64decode(sig_b64)
    except Exception:
        return None
    expected = hmac.new(settings.warden_secret_key.encode("utf-8"), body, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    return json.loads(body)
