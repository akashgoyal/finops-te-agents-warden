# Warden — demo video script (v2, under 3 minutes)

**Target length:** under 3:00. **Track:** Fortified Enterprise Fleet.

**Rewritten against the hackathon page's literal requirements** — the
first draft covered the architecture in more depth than required and,
critically, never actually showed GCP Console. That's not optional:

> Must demonstrate the backend is running on Google Cloud (i.e.:
> Google Cloud Console, Cloud Run dashboard, Vertex AI logs, URL of
> .run, etc.)

Required beats, all present below: **problem → value proposition →
app in action → proof it's on Google Cloud.**

**The one moment the whole video is built around:** a live call gets
**blocked**, and a second agent **decides in real time** whether to
retry it through the correctly-scoped agent or abort. If one shot gets
a re-take, it's that one — everything else can be tightened, this
can't be cut.

---

## 0:00–0:15 — The problem

**Screen:** 2 seconds each on real news screenshots (see sourcing note
below), then cut to face-to-camera or a title card.

**Say:**
> "In 2026, corporate agent fleets started getting real spending
> authority — and real incidents followed. An assistant exploited a
> booking system. Agents were caught exploiting their own
> infrastructure. Every framework for fixing this — Google's Agent
> Payments Protocol, NIST's agent-identity work — converges on the
> same idea: verifiable, task-bounded authorization for what an agent
> can spend, and on what."

> **Sourcing note:** these must be genuine screenshots of real
> published articles, captured yourself — no mockups, no recreated
> headlines. Two real, checked sources: the gym-booking API exploit
> ([Fox News](https://www.foxnews.com/tech/ai-agent-hacks-gym-system-move-up-waitlist)),
> and the OpenAI-agent-via-Hugging-Face-breach incident
> ([The Hacker News](https://thehackernews.com/2026/07/openai-agent-used-exposed-credentials.html)).

---

## 0:15–0:30 — Value proposition

**Screen:** the architecture page's Figure 1 (the pipeline image), or
straight to the live dashboard if you'd rather cut a beat.

**Say:**
> "Warden is that idea, built and running: an authorization gateway
> for a Travel & Expense agent fleet on Gemini 3.5, Google's ADK,
> Cloud Run, and Firestore. Every tool call — search a flight, hold a
> room, charge a card — gets checked before it executes, not after
> Finance finds it on the statement."

---

## 0:30–1:35 — Demo of the app in action (the centerpiece, ~65s)

**Screen:** the live Cloud Run URL, in a real browser tab —
**say the URL out loud once here.**

**Action:** click the **AUS → CHI** trip pill. Don't narrate the first
few steps — let search/booking/payment/hotel visibly clear.

**Say (brief, over the quick steps):**
> "This is deployed and live right now. Gemma clears the obvious calls
> for free — no paid model touches a call that's plainly in scope."

**Beat — the block (let it happen on screen, don't cut away):**
`hotel_agent` attempts `payments.charge`. Point at the **red BLOCK**
card the instant it appears.

**Say:**
> "hotel_agent was only ever scoped to search and hold a room. It just
> tried to charge a card directly — Gemini's review catches it."

**Beat — the orchestrator (the highlight):** point at the violet
orchestrator card / "Recovering — routing through payment_agent…"

**Say:**
> "This part isn't scripted. A second agent decides live whether
> retrying through the correctly scoped agent is reasonable — finds
> payment_agent is the only agent actually authorized for this tool,
> and the trip continues through it instead. Decided at runtime, not
> hand-coded per route."

**Action:** let the trip finish. Quick hover on the Transactions card's
red node and the Google Platform column (2–3s each) — real registry
lookups, real Gemini API calls, nothing simulated.

---

## 1:35–2:10 — Proof this is really on Google Cloud, part 1: Cloud Run (required, ~35s)

**This is the segment the hackathon page explicitly requires — don't
cut it for time.** See the exact GCP Console links to have ready,
below.

**Action:** switch to a second tab, already logged into
**console.cloud.google.com**, pre-navigated to the Cloud Run service
page for `warden` (see links below — do this *before* recording so
you're not waiting on page loads on camera).

**Say:**
> "And this isn't a claim — here's Cloud Run Console: the `warden`
> service, region us-central1, the exact revision that's currently
> serving 100% of traffic, and the same `.run.app` URL I just ran the
> demo on."

**Action:** click into the **Logs** tab — scroll to show real request
log lines from the trip you just ran (timestamps should match).

**Say:**
> "Real request logs from the run you just watched — not a local
> server standing in for this."

---

## 2:10–2:40 — Proof, part 2: Agent Identity + Memory Bank on Vertex AI (~30s)

**Action:** switch to Cloud Logging, filtered to the
`reasoningEngines` resource (link below), or run the verification
snippet live in a terminal (`agent_engine/README.md` has it) — either
shows the same thing.

**Say:**
> "One more piece of proof, on Vertex AI specifically: I deployed this
> same reviewer to Agent Engine and read the live resource's own spec
> back — it's running under its own dedicated IAM identity, not a
> shared service account, and it has a Memory Bank for persistent
> context, automatically. Not configuration I wrote — this is what
> Vertex AI provisions the moment you deploy an agent there."

**Action (if showing the terminal instead of/alongside Console):** run
the verification query live, let the real `BLOCK` decision print on
screen.

> **Reminder — do this right after recording, not later:** this
> resource doesn't scale to zero like Cloud Run. Delete it once the
> take is in the can:
> ```
> cd agent_engine && GOOGLE_CLOUD_PROJECT=finops-te-agent-warden .venv/bin/python -c "
> import vertexai
> from vertexai import agent_engines
> vertexai.init(project='finops-te-agent-warden', location='us-central1')
> agent_engines.delete('projects/330594494974/locations/us-central1/reasoningEngines/5550094453722578944', force=True)
> "
> ```

---

## 2:40–2:55 — Close

**Screen:** GitHub repo, or the architecture page.

**Say:**
> "Warden: an authorization gateway for an agentic fleet, built on
> Gemini, ADK, Cloud Run, Firestore, and Vertex AI, that fails closed
> instead of failing open. Repo, live link, and a full write-up are
> below."

**On-screen end card:** GitHub URL, live Cloud Run URL, and the
published dev.to post:
https://dev.to/akash_goyal/how-i-built-warden-an-authorization-gateway-for-agentic-fleets-on-google-cloud-48lp

---

## GCP links to have open before recording

Pre-navigate to these — don't type them live on camera, and don't rely
on a cold page load mid-take.

1. **Cloud Run service overview** (shows region, URL, traffic %, revision):
   `https://console.cloud.google.com/run/detail/us-central1/warden/metrics?project=finops-te-agent-warden`
2. **Cloud Run logs** (shows real request logs):
   `https://console.cloud.google.com/run/detail/us-central1/warden/logs?project=finops-te-agent-warden`
3. **Cloud Run revisions tab** (alternative/backup — shows the specific revision serving traffic):
   `https://console.cloud.google.com/run/detail/us-central1/warden/revisions?project=finops-te-agent-warden`
4. **Firestore data browser** (optional third proof — transactions/audit_log collections):
   `https://console.cloud.google.com/firestore/databases/-default-/data/panel?project=finops-te-agent-warden`
5. **Vertex AI Agent Engine resource** — the Console has moved this
   under the newer Gemini Enterprise Agent Platform surface, per
   Google's own [tracing docs](https://docs.cloud.google.com/agent-builder/agent-engine/manage/tracing):
   `https://console.cloud.google.com/agent-platform/runtimes?project=finops-te-agent-warden`
   — select `warden-policy-reviewer`, then the **Traces** tab. Sourced
   from Google's docs, not a guess, but still not clicked through with
   a live login this session — confirm it resolves before recording.
   **Fallback that *is* fully verified** (it's what the deploy script
   itself printed): the Cloud Logging link below.
   `https://console.cloud.google.com/logs/query;query=resource.labels.reasoning_engine_id%3D%225550094453722578944%22?project=finops-te-agent-warden`
6. **The live URL itself** (say it out loud in the demo segment):
   `https://warden-330594494974.us-central1.run.app` (or the equivalent
   `https://warden-5eio2cxkqa-uc.a.run.app` — both resolve to the same
   service; both re-checked live just now, both 200)

**If the Cloud Run deep links 404 or look stale** (Console URLs shift
occasionally): go to `console.cloud.google.com/run`, select project
`finops-te-agent-warden`, click into the `warden` service manually —
same destination, zero risk of showing a broken link on camera.

**Agent Engine resource, redeployed for this video**: currently live at
`projects/330594494974/locations/us-central1/reasoningEngines/5550094453722578944`,
verified working (`effectiveIdentity` is a dedicated IAM service
account, `memoryBankConfig` present, a live query returns the correct
`BLOCK` decision). **Delete it right after recording** — see the
reminder in the 2:10–2:40 segment above; it's the one piece of this
project's infrastructure that doesn't scale to zero.

## Shot list summary

1. Real news screenshots → talking head (0:15)
2. Value prop, brief (0:15)
3. **Live dashboard: click AUS → CHI, full trip uninterrupted** (1:05) — protect this take
4. **GCP Console: Cloud Run overview → Logs tab** (0:35) — required, don't cut
5. **Agent Engine proof: Console/Logs or live terminal query** (0:30)
6. Close card (0:15)

## Notes

- Sums to ~2:55 — 5s of margin under the 3:00 target. Tight; if a take
  runs long, trim the live-run narration first (segment 3), not the
  two GCP-proof segments.
- Record the Cloud Run Console segment as its own clean take, right
  after finishing a live trip, so the log timestamps visibly match
  what was just demoed on screen.
- The Agent Engine `agent-platform/runtimes` link above is sourced
  from Google's own docs, not guessed, but still hasn't been clicked
  through live this session — confirm it resolves *before* you're
  recording, not during. The Cloud Logging link and the live terminal
  query are both verified working right now and make a safe fallback
  or replacement for that whole segment.
- Checked again just now: a Cloud Trace query for this reasoning
  engine still comes back empty, even with the full tracing env vars
  now set on the resource (see `agent_engine/README.md`) — so don't
  plan on showing a trace in the Console; Identity + Memory Bank
  remain the two things this segment can actually prove.
- If you want the longer, more architecture-detailed cut instead of
  this one, an earlier draft is in git history (commit `53ec929`) —
  covers the backend-swap design in more depth, runs ~4:05, predates
  the GCP Console proof segments this version adds.
