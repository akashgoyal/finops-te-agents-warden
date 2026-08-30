---
title: Warden — an authorization gateway for agentic fleets, built on Google Cloud
published: false
tags: googlecloud, ai, agents, security
cover_image:
---

> **Before publishing:** dev.to can't read local file paths. For each
> `![...](blog-images/...)` image below, drag that file into the dev.to
> editor (or paste it) — it'll give you back a CDN URL — and swap it in.
> Do the same for one image up top as your `cover_image`.

Warden is a submission to the **All Things Agentic Hackathon**
(Fortified Enterprise Fleet track): an authorization gateway that sits
in front of a fleet of task agents and checks every tool call — search
a flight, hold a booking, charge a card — before it executes, not
after.

**Live app:** https://warden-330594494974.us-central1.run.app
**Architecture walkthrough:** https://akashgoyal.github.io/aiml/blog/warden-architecture.html
**Source:** https://github.com/akashgoyal/finops-te-agents-warden

## The problem, in two real headlines

2026 didn't wait long to produce examples of agents doing things
nobody actually authorized:

![An AI agent hacked a gym's booking system to move itself up a waitlist](blog-images/0_foxnews_ss.png)
*[Fox News: "AI agent hacks gym system to move up waitlist"](https://www.foxnews.com/tech/ai-agent-hacks-gym-system-move-up-waitlist)*

![An OpenAI agent used exposed credentials across four services during a breach](blog-images/0_hackernews_ss.png)
*[The Hacker News: "OpenAI Agent Used Exposed Credentials Across Four Services During Hugging Face Breach"](https://thehackernews.com/2026/07/openai-agent-used-exposed-credentials.html)*

Neither agent was "hacked" from outside. Both just did something
technically possible that nobody had actually authorized. That's the
gap Warden targets — for a workflow every company already has strict
policy for: **Travel & Expense**.

## What Warden actually does

Think of it as a bouncer standing between every agent in the fleet and
the tools it's asking to use. Each attempted call goes through, in
order:

1. A **hard-limit check** — plain code, no model, no cost. A payment
   over the cap stops the trip and waits for a human, full stop.
2. A **cheap first pass** (Gemma) — clears the obvious, in-scope calls
   for free.
3. A **careful review** (Gemini, via Google's Agent Development Kit)
   — anything ambiguous or out-of-scope gets read against the fleet's
   actual policy document and a real decision, with a reason.
4. If it's **blocked**, a second agent decides — live, not scripted —
   whether to retry the same step through the agent that's actually
   allowed to do it, or abort the trip.

Every decision, allowed or blocked, is written to a tamper-evident log
before anything happens next.

![Warden's full request-flow architecture — intercept, guardrail, triage, review, orchestrator, ledger](blog-images/8_architecture_pipeline.png)
*The full pipeline. A deeper walkthrough — including two scenario
flows and the Google Cloud stack behind each stage — is on the
[architecture page](https://akashgoyal.github.io/aiml/blog/warden-architecture.html).*

## Seeing it live

The dashboard is a real console, not a mockup — click a trip and watch
the fleet run:

![Warden's dashboard at rest, before a trip is triggered](blog-images/1_dashboard_at_rest.png)
*The live app, idle. Four panels: what the traveler sees, the live
call trace, past transactions, and every touch of Google
infrastructure as it happens.*

![A completed trip where the hotel agent's payment attempt was blocked and recovered](blog-images/2_dashboard_processed.png)
*A full AUS → CHI trip. Step 6: `hotel_agent` tries to charge a card
directly — outside its job. It's blocked. Step 7: a second agent
decides to retry the same charge through `payment_agent` instead. The
trip finishes.*

Zooming into the two moments that matter:

![The BLOCK decision on the hotel agent's payment attempt, with the reviewer's rationale](blog-images/3_hotel_payment_closeup.png)
*Gemini's actual reasoning: `hotel_agent` is scoped to search and hold
a room, not to charge anything.*

![The orchestrator's live recovery decision, routing the charge through the correct agent](blog-images/4_payment_retry_closeup.png)
*Not a hand-coded fallback — a second model call, at runtime, deciding
this specific retry is safe because `payment_agent` is the one agent
actually authorized for it.*

## Local development vs. what's actually running on Google Cloud

While building this, day-to-day iteration ran against small open
models on a laptop (via [Ollama](https://ollama.com)) — purely so
changes could be tested instantly, for free, without touching a cloud
project. That's a developer convenience, not part of the submission's
cloud story, and it's worth being upfront about that distinction.

**What's actually deployed and judged** is a separate, real thing:
Cloud Run running the same code, calling Gemini through Google AI
Studio's genuine free tier, with Firestore as the backing store. No
stub mode, no mocked responses.

![The deployed Cloud Run revision, showing MODEL_BACKEND=gemini and other real deploy config](blog-images/6_gcp_run_revisions.png)
*The actual deployed revision's config — `MODEL_BACKEND=gemini`,
1 CPU, 1GiB, port 8080. Not asserted, read straight off the resource.*

![Cloud Run request metrics, instance count dropping to zero between demo runs](blog-images/6_gcp_run_metrics.png)
*Container instance count returns to zero between runs — this costs
nothing while nobody's using it.*

![Real Cloud Run request logs from an actual trip run](blog-images/6_gcp_run_logs.png)
*Real request logs — not a local server standing in for the cloud
deployment.*

## The audit trail is real Firestore, not memory

Every agent's declared scope, and every decision Warden makes, is
written to Firestore — so restarting the service, or Cloud Run
scaling to zero, never loses the record.

![Firestore document showing hotel_agent's declared scope: hotel.search and hotel.hold only](blog-images/7_firestore_db_agents-1.png)
*The actual registry entry that made the block possible —
`hotel_agent`'s allowed tools, stored as data, not hardcoded logic
somewhere in the reviewer.*

![Firestore document showing a fully persisted transaction record with the block decision and reviewer rationale](blog-images/7_firestore_db_transactions.png)
*One real trip, fully persisted — every step, its decision, the
reviewing model, and the signed token, exactly as the dashboard read
them back.*

## Model Armor: is it worth using here?

[Model Armor](https://docs.cloud.google.com/model-armor/overview) is
Google Cloud's own screening layer — it inspects prompts and
responses for injection attempts, jailbreaks, and sensitive data
before and after they reach a model. Warden wires it into the
reviewer's calls, and it's genuinely working, not just configured:

![Model Armor badge on the blocked hotel agent call, showing the real template name](blog-images/5_vertex_model_armor_hotel_agent.png)
*The `warden-prompt-response` badge is read live off the actual
review result — not a static label added for the screenshot.*

![Model Armor badge also present on the orchestrator's retry decision](blog-images/5_vertex_model_armor_payment_agent.png)
*Same screening on the recovery decision right after.*

![Real Vertex AI request logs from the reviewer, confirming genuine Vertex traffic](blog-images/5_vertex_model_armor_reasoning_engine.png)
*Confirmed in Cloud Logging too — this is a real call to
`gemini-2.5-flash` through Vertex AI, not a simulated one.*

**So, better or not?** As a security layer, yes — it's a real extra
check most agent demos skip entirely. But it only attaches when calls
go through Vertex AI directly, not the free Google AI Studio path the
live deployment uses — and Vertex AI bills from the first token, with
no free tier. That's why it's shipped as a working, opt-in option you
can turn on locally, rather than the default on the always-on public
deployment. A cost tradeoff, not a functionality gap.

## What judges should actually take away

- The audit trail, agent registry, and transaction history are real
  Firestore data — not held in memory, not reset on restart.
- The reviewer and the recovery decision are real Google ADK agents
  reasoning over an actual policy document — not if/else logic
  dressed up as AI.
- The live deployment runs on Cloud Run, on Gemini, for real — nothing
  shown above is stubbed.
- Model Armor screening is demonstrated and verified working, kept
  opt-in for cost reasons already explained above.
- A real per-agent cryptographic identity (and, as a bonus, persistent
  memory) is also demonstrated on a separate Vertex AI Agent Engine
  deployment — a different, more involved setup, so it's kept
  additive rather than part of the main live path.
- One honest gap: full trace-level observability (the kind
  OpenTelemetry tooling expects) is partially confirmed, not fully —
  called out directly rather than glossed over.

## How to set up the Google Platform tools, briefly

Here's what actually gets configured, tool by tool, if you want to run
this yourself. Exact commands are in the repo's README — this is the
map of what each piece is for.

**Cloud Run** — hosts the gateway itself, scaled to zero when idle.
- Confirm the project has billing linked: [Billing console](https://console.cloud.google.com/billing).
- Enable the Cloud Run API from the [API Library](https://console.cloud.google.com/apis/library).
- Deploy with `--min-instances=0` so it costs nothing while no one's
  using it — one script call in this repo does it.
- The model backend, project ID, and secret key are set as deploy-time
  environment variables, not baked into the image — see them for
  yourself on the [Cloud Run console](https://console.cloud.google.com/run).

**Firestore** — the agent registry and the audit/transaction ledger.
- Create a **Native mode** database from the [Firestore console](https://console.cloud.google.com/firestore) — Datastore mode won't work here.
- Run the repo's seed script once to write each agent's declared
  scope in as data (what you saw in the screenshot above) — nothing
  about scopes is hardcoded in the reviewer's code.
- Leave the project ID blank in local dev and everything falls back to
  in-memory automatically — no Firestore calls, no accidental writes.

**Vertex AI + Model Armor** — the opt-in screening layer.
- Enable the Vertex AI and Model Armor APIs from the [API Library](https://console.cloud.google.com/apis/library).
- Create a Model Armor template (prompt-injection/jailbreak filters,
  sensitive-data checks) — one `gcloud model-armor templates create`
  call, done once.
- Point the reviewer at Vertex AI instead of the free Gemini Developer
  API, and pass that template's name in on each call — that's the
  entire integration surface.
- Know before turning this on: Vertex AI's Gemini calls bill from the
  first token, with no free tier like Google AI Studio has.

**Vertex AI Agent Engine** *(optional)* — a real per-agent identity.
- From the [Vertex AI console](https://console.cloud.google.com/vertex-ai), or via the SDK, deploy the same
  reviewer agent as a managed Agent Engine resource.
- Google provisions a dedicated IAM service account for that specific
  deployed agent automatically — not something you configure by hand.
- It also comes with a persistent Memory Bank for cross-session
  context, at no extra setup.
- Unlike Cloud Run, this resource stays provisioned — delete it when
  you're done demonstrating it, unless you've checked current pricing.

## Links

- **Live app:** https://warden-330594494974.us-central1.run.app
- **Architecture walkthrough:** https://akashgoyal.github.io/aiml/blog/warden-architecture.html
- **Source:** https://github.com/akashgoyal/finops-te-agents-warden
