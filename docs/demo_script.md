# Warden — demo video script (first draft)

**Target length:** ~4 minutes. **Track:** Fortified Enterprise Fleet.
**Judging weights to keep in mind while narrating:** Innovation &
Operational Utility 40% · Architectural Discipline & Tech Stack 30% ·
Demo & Production Readiness 30%.

**Core thesis to land, once, early, in plain words:** *Warden is the
authorization gateway a Finance Ops team would actually require before
letting an agent fleet touch corporate spend — every tool call gets
checked before it executes, not after Finance finds it on the
statement.*

**The one moment the whole video is built around:** a live call gets
**blocked**, and a second agent **decides in real time** whether to
retry it through the correctly-scoped agent or abort the trip. Not
narrated after the fact — the recovery has to happen on screen, live,
against the real deployed backend. If one shot gets a re-take, it's
that one.

---

## 0:00–0:20 — Hook: the problem, not the product

**Screen:** black slide or your face to camera, no UI yet.

**Say:**
> "In 2026, corporate agent fleets started getting real spending
> authority — and real incidents followed. An assistant exploited a
> booking system. Agents were caught exploiting their own
> infrastructure. The fix everyone from Google's Agent Payments
> Protocol to NIST is converging on is the same: verifiable,
> task-bounded authorization for what an agent can spend, and on what.
> This is Warden — a working version of that idea, for the workflow
> every finance org already has a policy for: travel and expense."

---

## 0:20–0:55 — Architecture, fast (30–35s)

**Screen:** `docs/architecture.html` (or the published Artifact) —
Figure 1, the request-flow diagram. Cursor traces the path as you talk.

**Say:**
> "Five fleet agents — search, booking, hotel, cab, payment — every
> tool call routes through one Gateway on Cloud Run. First, a
> deterministic guardrail — plain code, no model, checking a hard
> dollar cap. Then Gemma triages what's left for free. Only genuinely
> ambiguous calls reach an ADK reviewer backed by Gemini 3.5 Flash.
> Every decision — allow, block, or escalate — is signed and written to
> a hash-chained Firestore ledger."

**Cut to:** Figure 2 (backend swap) for one sentence —

> "That reviewer is one agent definition — the same code runs on
> Ollama locally, Gemini in production, or Vertex AI with Model Armor
> screening attached, just by changing one setting."

*(This single breath covers: ADK, Gemini 3.5 Flash, Cloud Run,
Firestore — all four hackathon-required technologies — before the demo
even starts.)*

---

## 0:55–1:10 — Open the live dashboard

**Screen:** navigate to the live Cloud Run URL
(`warden-330594494974.us-central1.run.app`) in a real browser tab —
**not localhost**. Say the URL out loud once, on screen, so it's
unambiguous this is the deployed service.

**Say:**
> "This is deployed, live, right now — not a local demo. Four columns:
> what the traveler sees on the left, Warden's own decision trace and
> transaction history in the middle, and on the right — every real
> touch of Google's infrastructure this fleet makes, as it happens."

**Action:** briefly hover/point at each of the four pill columns by
name (App, Live Agent Trace, Transactions, Google Platform) so a viewer
can map the labels before the fast part starts.

---

## 1:10–2:40 — THE live run (this is the demo)

**Action:** click the **AUS → CHI** trip pill. This is the route with
the built-in scope violation — don't narrate over the first few steps,
let them visibly tick past.

**Say (while search/booking/hotel/payment steps clear via triage):**
> "Search, booking, payment, hotel — Gemma clears these in milliseconds,
> for free. No paid model touches a call that's plainly in scope."

**Beat — the block (let this actually happen on screen, don't cut away):**
`hotel_agent` attempts `payments.charge`. Point at the **red BLOCK**
card the instant it appears in Live Agent Trace.

**Say:**
> "There it is — hotel_agent was only ever scoped to search and hold a
> room. It just tried to charge a card directly. Gemini's review
> catches it: blocked, in scope of its own policy, no cap, no rule —
> genuine reasoning."

**Beat — the orchestrator (the highlight moment):** point at the
violet orchestrator card / "Recovering — routing through payment_agent…"

**Say:**
> "This is the part that isn't scripted. A second agent — the
> orchestrator — decides live whether retrying through the correctly
> scoped agent is reasonable, or the trip should abort. It finds
> payment_agent is the only agent actually scoped for this tool,
> confirms the retry makes sense, and the trip continues — through a
> different agent than the one that started it. That's the real answer
> to 'can agent execution order vary': yes, and it's decided at
> runtime, not hand-coded per route."

**Action:** let the trip finish (cab search/book, completion).

**Action:** switch to the **Transactions** panel below. Click the
just-finished card to replay it in the trace panel above.

**Say:**
> "Every trip is one card — the full agent order as a linked list, not
> a log line. Hover any node —"

**Action:** hover the red hotel node, then the orchestrator node.

> "— agent, tool, the actual call arguments, the model's rationale, and
> for an allowed call, a signed, task-bounded token, right here."

**Cut to Google Platform column**, scroll to show a few real entries.

**Say:**
> "And this column isn't decorative — every entry here is a real event
> the gateway published: a Firestore registry permission check, the
> actual Gemini API calls, the Firestore ledger write. Nothing here is
> simulated for the video."

*(Optional 10s, if time allows: trigger **SFO → SIN** briefly to show
the escalate path — a flight alone crosses the $2,000 cap, guardrail
fires deterministically, trip pauses for a human, no model even runs.
Cut fast if you're tight on time — the block→retry moment above is the
one that has to land.)*

---

## 2:40–3:15 — What's under the hood judges won't see by clicking around

**Screen:** Figure 3 of the architecture diagram (Cloud Run vs. Agent
Engine), or a terminal window with the verification output if you'd
rather show a real artifact.

**Say:**
> "Two more pieces, verified but not in this live call path, on
> purpose. I deployed this same reviewer to Vertex AI Agent Engine and
> read the resource's own spec back: it gets a dedicated IAM identity —
> Agent Identity — and a Memory Bank for persistent cross-session
> context, automatically, just from choosing that hosting target. And
> Model Armor — prompt and response screening — is wired in as a third
> backend option, verified end-to-end against the exact same
> block-and-retry scenario you just watched."

*(This is where the Fortified Enterprise Fleet track's named components
— Agent Gateway, Registry, Runtime, Identity, Memory Bank, Model
Armor, Observability — get their explicit callout. Consider a 3–4
second full-screen cut to the README's component-mapping table here if
it reads clearly on camera.)*

---

## 3:15–3:45 — Production-readiness, honestly

**Say (over the dashboard, calm, no urgency):**
> "None of this was theoretical. Building this against real Google
> Cloud infrastructure surfaced real bugs — an unbounded network call
> that hung a trip for two minutes with no error, a pip resolver
> backtracking through sixty package versions and timing out a build,
> Google's own edge silently intercepting a literal `/healthz` health
> check path. Every one of those is root-caused and fixed in the repo,
> not papered over — because the whole premise of Warden is that
> failure handling has to be real, not assumed."

---

## 3:45–4:00 — Close

**Screen:** back to the dashboard, or the GitHub repo.

**Say:**
> "Warden: an authorization gateway for an agentic fleet, built on
> Gemini, ADK, Cloud Run, and Firestore, that fails closed instead of
> failing open. Repo and live link are below."

**On-screen text/end card:** GitHub URL, live Cloud Run URL.

---

## Shot list summary (for whoever's screen-recording)

1. Talking head / title card — hook (0:20)
2. `docs/architecture.html` Figure 1, then Figure 2 (0:35)
3. Live dashboard, deployed URL, four columns named (0:15)
4. **Click AUS → CHI, let the full trip run uninterrupted on screen** (1:30) — the take to protect
5. Transactions card click-to-replay + hover popovers (0:20)
6. Google Platform column, scrolled to show real entries (0:10)
7. Architecture diagram Figure 3 (Agent Engine) or terminal proof (0:35)
8. Talking head — production-readiness honesty beat (0:30)
9. Close card (0:15)

## Notes for the next draft

- Timings above sum to ~4:10 — trim the optional SFO→SIN insert first,
  then tighten the architecture recap (0:20–0:55) if still over.
- Say the deployed URL out loud on camera once — a judge should never
  have to wonder if this is running locally.
- If re-recording the live-run take, clear `audit_log`/`transactions`
  in Firestore first (or just trigger a fresh trip) so the stats bar
  and card list both start from a clean, small number on screen —
  matches the "numbers and record should stay aligned" fix already
  shipped, and looks more deliberate on camera than a big pre-existing
  count.
