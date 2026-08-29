#!/usr/bin/env bash
# One-time setup for MODEL_BACKEND=vertex — Vertex AI + Model Armor prompt/
# response screening. Optional and separate from scripts/setup_gcp.sh on
# purpose: Model Armor has no free tier, and Vertex AI's Gemini calls are
# billed differently (metered from the first token) than the Gemini
# Developer API / AI Studio key the default "gemini" backend uses. Run
# this only if you want the vertex backend; ollama and gemini both work
# without it.
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT first}"
LOCATION="${VERTEX_LOCATION:-us-central1}"
TEMPLATE_ID="${MODEL_ARMOR_TEMPLATE_ID:-warden-prompt-response}"

echo "==> Using project: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

echo "==> Enabling required APIs"
gcloud services enable aiplatform.googleapis.com modelarmor.googleapis.com

echo "==> Making one real Vertex AI call to provision the default service agent"
# The service-<PROJECT_NUMBER>@gcp-sa-aiplatform.iam.gserviceaccount.com
# agent doesn't exist until Vertex AI has actually been used once —
# verified live: granting IAM to it before this fails with "Service
# account ... does not exist," even with the API freshly enabled.
python3 -c "
from google import genai
client = genai.Client(vertexai=True, project='$PROJECT_ID', location='$LOCATION')
client.models.generate_content(model='gemini-2.5-flash', contents='say OK')
print('Service agent provisioning call succeeded.')
" || echo "    (non-fatal if this fails — retry the IAM grant below after a minute)"

echo "==> Granting Model Armor access to the Vertex AI service agent"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com" \
  --role='roles/modelarmor.user' --quiet

echo "==> Creating the Model Armor template (prompt injection/jailbreak, malicious URIs, RAI filters, sensitive data)"
gcloud model-armor templates create "$TEMPLATE_ID" \
  --location="$LOCATION" \
  --malicious-uri-filter-settings-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-confidence-level=MEDIUM_AND_ABOVE \
  --basic-config-filter-enforcement=enabled \
  --rai-settings-filters=filterType=HATE_SPEECH,confidenceLevel=MEDIUM_AND_ABOVE \
  --rai-settings-filters=filterType=HARASSMENT,confidenceLevel=MEDIUM_AND_ABOVE \
  --rai-settings-filters=filterType=SEXUALLY_EXPLICIT,confidenceLevel=MEDIUM_AND_ABOVE \
  --rai-settings-filters=filterType=DANGEROUS,confidenceLevel=MEDIUM_AND_ABOVE \
  || echo "    (already exists — skipping)"

TEMPLATE_NAME="projects/${PROJECT_ID}/locations/${LOCATION}/templates/${TEMPLATE_ID}"
echo ""
echo "==> Done. Add to .env:"
echo ""
echo "MODEL_BACKEND=vertex"
echo "VERTEX_LOCATION=${LOCATION}"
echo "MODEL_ARMOR_PROMPT_TEMPLATE=${TEMPLATE_NAME}"
echo "MODEL_ARMOR_RESPONSE_TEMPLATE=${TEMPLATE_NAME}"
echo ""
echo "Note: gemini-3.5-flash (config.py's default gemini_model) 404s on"
echo "this project's Vertex AI catalog — only up to gemini-2.5-flash is"
echo "accessible, verified via client.models.list(). warden/config.py's"
echo "vertex_gemini_model setting handles this; no action needed unless"
echo "your project has broader Vertex AI model access than this one did."
