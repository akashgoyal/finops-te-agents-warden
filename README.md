# Warden

An authorization gateway for a corporate agentic fleet — every tool
call an agent makes gets checked before it executes, not after. Built
for the **All Things Agentic Hackathon**, Fortified Enterprise Fleet
track, on a Travel & Expense fleet as the concrete example.

## Problem

Corporate agent fleets are getting real spending authority, and 2026
has already had real incidents of agents taking actions nobody
authorized — an assistant exploiting a fitness-booking system, agents
caught exploiting their own infrastructure. Today, nothing stops a
scope-violating tool call before it executes.

## Solution

Warden intercepts every tool call — search a flight, hold a booking,
charge a card — before it reaches the real tool. A deterministic
hard-limit guardrail runs first, then a tiered Gemma/Gemini review
against the fleet's declared policy. An allowed call gets a signed,
task-bounded token; a blocked call goes to an orchestrator agent that
decides live whether to retry through the correctly-scoped agent or
abort. Every decision lands in a hash-chained Firestore ledger.

## Google platform tools used

- **Gemini + Gemma** — the tiered review pipeline
- **Google ADK** — the reviewer and orchestrator agents
- **Cloud Run** — hosts the live gateway
- **Firestore** — registry, audit ledger, transactions
- **Secret Manager** — deployed API key/secret storage
- **Vertex AI Model Armor** — inline prompt/response screening (opt-in)
- **Vertex AI Agent Engine** — Agent Identity + Memory Bank (separate deployment)
- **Cloud Build + Artifact Registry** — build pipeline

## Models used

- `gemini-3.5-flash` — reviewer + orchestrator, deployed default
- `gemma-4-26b-a4b-it` — triage, deployed default
- `gemini-2.5-flash` — via Vertex AI, for Model Armor + Agent Engine
  (this project's Vertex catalog ceiling)

## Google SDK used

- `google-adk` — the two agents
- `google-genai` — Gemini/Gemma calls
- `google-cloud-firestore` — registry, ledger, transactions
- `google-cloud-aiplatform` — Vertex AI, Model Armor, Agent Engine

## How to test

```bash
make install && make test    # automated, stub mode, no network calls
```

Or trigger a real trip on the live app below — no login needed. Click
**AUS → CHI** and watch `hotel_agent`'s payment attempt get blocked,
then recovered live through `payment_agent`.

## How to set up

```bash
# local, free, real models via Ollama
make install && make dev

# cloud, once you have a GCP project
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_API_KEY=...          # from AI Studio
export WARDEN_SECRET_KEY=...       # any random string
make deploy
python -m scripts.seed_registry
```

`MODEL_BACKEND` switches between `ollama` (local), `gemini` (AI
Studio, deployed default), and `vertex` (Vertex AI + Model Armor,
opt-in). See `.env.example` for every variable.

## Links

- **Live app** — https://warden-330594494974.us-central1.run.app
- **Demo video** — https://youtu.be/ebTWWi_bfEc
- **Blog write-up** — https://dev.to/akash_goyal/how-i-built-warden-an-authorization-gateway-for-agentic-fleets-on-google-cloud-48lp
- **Architecture walkthrough** — https://akashgoyal.github.io/aiml/blog/warden-architecture.html
