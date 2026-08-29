#!/usr/bin/env bash
# One-time GCP setup — run once before your first deploy. No credits needed,
# everything here fits Google's Always Free tier at hackathon-demo traffic.
# Requires: gcloud CLI, logged in (`gcloud auth login`), a project selected.
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT first}"
BILLING_ALERT_USD="${BILLING_ALERT_USD:-5}"

echo "==> Using project: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

echo "==> Enabling required APIs"
# No aiplatform.googleapis.com here on purpose — Warden calls the Gemini
# Developer API (AI Studio key) rather than Vertex AI's hosted endpoint,
# specifically to stay on the free tier. cloudbuild + artifactregistry are
# what `gcloud run deploy --source=.` uses under the hood to build and
# store the image; both have their own free allowances at this scale.
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbilling.googleapis.com

echo "==> Creating Firestore database (Native mode) if it doesn't exist"
gcloud firestore databases create --location=us-central1 --type=firestore-native || \
  echo "    (already exists — skipping)"

echo "==> Storing secrets"
echo -n "${GOOGLE_API_KEY:?Set GOOGLE_API_KEY first}" | \
  gcloud secrets create warden-google-api-key --data-file=- 2>/dev/null || \
  echo -n "$GOOGLE_API_KEY" | gcloud secrets versions add warden-google-api-key --data-file=-

echo -n "${WARDEN_SECRET_KEY:?Set WARDEN_SECRET_KEY first}" | \
  gcloud secrets create warden-secret-key --data-file=- 2>/dev/null || \
  echo -n "$WARDEN_SECRET_KEY" | gcloud secrets versions add warden-secret-key --data-file=-

echo "==> Granting the Cloud Run service account read access to both secrets"
# Creating a secret does NOT implicitly grant the default compute service
# account access to it — found live: deploy_cloud_run.sh got all the way
# through building and creating the revision, then failed with "Permission
# denied on secret ... must be granted Secret Manager Secret Accessor".
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for secret in warden-google-api-key warden-secret-key; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:${RUN_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet || echo "    (binding for $secret may already exist — non-fatal)"
done

echo "==> Billing budget alert at \$${BILLING_ALERT_USD} (tripwire, not an expectation)"
BILLING_ACCOUNT=$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingAccountName)')
gcloud billing budgets create \
  --billing-account="${BILLING_ACCOUNT#billingAccounts/}" \
  --display-name="warden-hackathon-tripwire" \
  --budget-amount="${BILLING_ALERT_USD}USD" \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=1.0 \
  || echo "    (budget already exists, or you'll need to set this one up in the console — non-fatal)"

echo "==> Done. Next: scripts/deploy_cloud_run.sh, then python -m scripts.seed_registry"
