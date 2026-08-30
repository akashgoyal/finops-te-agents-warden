# Agent Engine — real Agent Identity (and, it turns out, Memory Bank)

Deploys Warden's policy reviewer to Vertex AI Agent Engine, the only place
a real **Agent Identity** actually attaches. Separate, additive, opt-in —
see the module docstring in `deploy_reviewer.py` for why this isn't wired
into the main `warden/` gateway's live call path.

## What's verified, not assumed

Deployed for real (`projects/330594494974/locations/us-central1/reasoningEngines/3266347230180671488`)
and checked directly against the live resource, not the docs:

- **Agent Identity is real.** The resource's `spec.effectiveIdentity` is
  `service-330594494974@gcp-sa-aiplatform-re.iam.gserviceaccount.com` — a
  dedicated Google-managed service account/IAM principal for this specific
  deployed agent, distinct from the project's default compute service
  account `warden/`'s Cloud Run deployment runs as.
- **Memory Bank came along for free.** Not something this project asked
  for — the deployed resource's `contextSpec` includes a
  `memoryBankConfig` automatically, with real callable methods
  (`async_add_session_to_memory`, `async_search_memory`) confirmed present
  on the resource's own class-method spec. Closes the other named gap
  (persistent cross-session context) as a side effect of deploying here,
  not a separate integration.
- **It actually works.** Queried live with the exact scope-violation
  scenario the whole demo is built around (`hotel_agent` trying
  `payments.charge`) and got the correct decision back:
  `{"decision": "BLOCK", "rationale": "The 'hotel_agent' is not authorized
  to use the 'payments.charge' tool..."}`, via `gemini-2.5-flash` — same
  model-catalog ceiling on this project's Vertex AI access found earlier
  with Model Armor.
- **Observability: configured, not independently confirmed.**
  `AdkApp(enable_tracing=True)` sets `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true`
  on the deployed spec (visible in the resource's raw JSON), but a Cloud
  Trace API query for this project came back empty after a real call and
  a wait, with `cloudtrace.googleapis.com` confirmed enabled. Reporting
  this as configured-but-unconfirmed rather than claiming a trace was
  actually seen.

## Why a separate venv

`vertexai.agent_engines.AdkApp` requires `google-adk>=1.5.0`. The main
`warden/` path pins `google-adk==1.1.1` deliberately — that exact pin is
what fixed a real 25-30 minute Cloud Build hang from pip's resolver
backtracking (see the main `requirements.txt`'s own comment). Bumping the
shared dependency to satisfy this would risk destabilizing the
already-verified-working Cloud Run deployment, so this got its own,
completely isolated environment instead:

```bash
cd agent_engine
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Deploying

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
# needs a GCS staging bucket — created once:
#   gcloud storage buckets create gs://${GOOGLE_CLOUD_PROJECT}-agent-engine-staging \
#     --project=$GOOGLE_CLOUD_PROJECT --location=us-central1
.venv/bin/python deploy_reviewer.py
```

Prints the deployed resource name. Reuse it directly:

```python
import vertexai
from vertexai import agent_engines
vertexai.init(project="your-project-id", location="us-central1")
agent = agent_engines.get("projects/.../locations/us-central1/reasoningEngines/...")
for event in agent.stream_query(message="...", user_id="demo"):
    print(event)
```

## Cost — read before leaving this deployed

Unlike `warden/`'s Cloud Run deployment (`--min-instances=0`, scales to
$0 while idle) and the AI-Studio-backed `gemini` model backend (genuine
free tier), **Agent Engine is a managed, persistently-provisioned
resource** — it does not have the same scale-to-zero cost profile.
Delete it once you're done demonstrating it, unless you've confirmed
current Agent Engine pricing for your own project:

```bash
.venv/bin/python -c "
import vertexai
from vertexai import agent_engines
vertexai.init(project='your-project-id', location='us-central1')
# force=True needed if you've queried it at all — querying creates a
# child 'sessions' resource, and delete() without force refuses to
# remove a resource that still has children. Verified live: deleting
# right after the stream_query() test above hit exactly this.
agent_engines.delete('projects/.../locations/us-central1/reasoningEngines/...', force=True)
"
```

This repo's own deployment was created, verified live, and deleted again
within the same session — confirmed via `agent_engines.list()` returning
zero resources afterward. Nothing from this module is left running.
