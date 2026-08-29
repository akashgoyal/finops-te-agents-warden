#!/usr/bin/env bash
# Deploy Warden to Cloud Run — scaled to zero, so it costs nothing while
# nobody's calling it. Run scripts/setup_gcp.sh first.
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT first}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-warden}"

# --no-cpu-throttling: without this, Cloud Run only allocates CPU while
# actively handling a request/response cycle. POST /v1/trips/run returns
# immediately and does the real work in a FastAPI BackgroundTasks callback
# afterward — a classic Cloud Run + BackgroundTasks trap. Verified live: a
# real trip sat at 0/9 steps through 8 polls (~80s) with the container's
# own logs showing nothing but the polling GETs themselves, because the
# background task never got CPU time between requests to make progress.
gcloud run deploy "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --source=. \
  --min-instances=0 \
  --max-instances=1 \
  --memory=512Mi \
  --cpu=1 \
  --no-cpu-throttling \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},MODEL_BACKEND=gemini,WARDEN_STUB_MODE=false,GEMINI_MODEL=${GEMINI_MODEL:-gemini-flash-latest},GEMMA_MODEL=${GEMMA_MODEL:-gemma-4-26b-a4b-it}" \
  --set-secrets="GOOGLE_API_KEY=warden-google-api-key:latest,WARDEN_SECRET_KEY=warden-secret-key:latest"

echo "==> Deployed. min-instances=0 means it scales to zero between demo runs — no idle cost."
