"""Deploys Warden's policy reviewer to Vertex AI Agent Engine — the only
place a real Agent Identity (a strongly-attested, SPIFFE-based cryptographic
identity, each agent registered as its own IAM principal) actually attaches.

This is intentionally a SEPARATE, additive path — not a replacement for
warden/reviewer_agent.py, and not wired into the deployed Cloud Run
gateway's live call path. That gateway keeps running the same Agent
in-process (via ADK's InMemoryRunner) exactly as it does today, on whichever
of ollama/gemini/vertex MODEL_BACKEND is set — nothing here touches that.

Why a separate deployment target and not just a new MODEL_BACKEND value
(the way Model Armor was added): Agent Identity isn't a config flag on a
model call, it's a property of *where the agent runs*. Vertex AI Agent
Engine is a distinct managed runtime from Cloud Run — deploying here means
the reviewer's actual reasoning calls happen on Google's infrastructure,
addressed as its own resource, not inside Warden's own container. Calling
it from the gateway would mean a network hop to a separately-billed,
separately-versioned resource instead of an in-process call — a real
architecture change, not a toggle, so it's kept opt-in and demonstrated
here rather than defaulted into the submission's live deployment.

Usage:
    export GOOGLE_CLOUD_PROJECT=your-project-id
    python -m agent_engine.deploy_reviewer

Requires `pip install google-cloud-aiplatform[agent_engines,adk]` (already
satisfied by this repo's requirements.txt — google-cloud-aiplatform is a
transitive dependency of google-adk, and vertexai.agent_engines ships
inside it; verified installed, not assumed, before writing this).
"""

from __future__ import annotations

import os
import sys

# Reuse the real reviewer instruction verbatim — this should be recognizably
# the same reviewer as warden/reviewer_agent.py, not a redefinition that
# could quietly drift from it.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from warden.reviewer_agent import _INSTRUCTION  # noqa: E402

# Vertex AI Agent Engine is a Vertex AI product like the "vertex" model
# backend — subject to the same catalog gap found and verified there
# (warden/config.py's vertex_gemini_model comment): this project's Vertex
# AI access tops out at gemini-2.5-flash, every gemini-3.x model 404s.
_MODEL = os.environ.get("AGENT_ENGINE_MODEL", "gemini-2.5-flash")


def build_agent():
    from google.adk.agents import Agent

    return Agent(
        name="warden_policy_reviewer",
        model=_MODEL,
        description="Reviews agent tool calls against Warden's fleet policy — deployed for a real Agent Identity.",
        instruction=_INSTRUCTION,
    )


def deploy():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise SystemExit("Set GOOGLE_CLOUD_PROJECT first.")
    location = os.environ.get("VERTEX_LOCATION", "us-central1")

    # Agent Engine stages the packaged agent app through GCS before
    # building it into a deployed resource — verified live, not assumed:
    # agent_engines.create() raised ValueError("Please provide a
    # `staging_bucket`") without this.
    staging_bucket = os.environ.get(
        "AGENT_ENGINE_STAGING_BUCKET",
        f"gs://{project}-agent-engine-staging",
    )

    import vertexai
    from vertexai import agent_engines

    vertexai.init(project=project, location=location, staging_bucket=staging_bucket)

    agent = build_agent()
    # enable_tracing=True is deprecated — verified live: it only sets
    # GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY on the deployed spec,
    # and a real Cloud Trace query for this project came back empty.
    # Google's current tracing docs (docs.cloud.google.com/agent-builder/
    # agent-engine/manage/tracing) want these three env vars instead —
    # passed explicitly below so create() bakes them into the deployed
    # resource, not relying on the deprecated flag alone.
    app = agent_engines.AdkApp(agent=agent, enable_tracing=True)

    print(f"==> Deploying warden_policy_reviewer to Agent Engine ({project}/{location})")
    remote = agent_engines.create(
        app,
        requirements=["google-adk", "google-cloud-aiplatform[agent_engines]"],
        display_name="warden-policy-reviewer",
        description="Warden's ADK policy reviewer, deployed for a real Vertex AI Agent Identity.",
        env_vars={
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
            "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
        },
    )

    print("==> Deployed:", remote.resource_name)
    return remote


if __name__ == "__main__":
    deploy()
