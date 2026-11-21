#!/usr/bin/env bash
# Build + deploy the SentinelDesk Streamlit console to Cloud Run. Run from anywhere.
#   TAG=full MAX_KB=0 ./cloudrun/console/deploy.sh          (full KB)
#   TAG=kb15k MAX_KB=15000 ./cloudrun/console/deploy.sh     (faster build)
#   SKIP_BUILD=1 TAG=full ./cloudrun/console/deploy.sh       (redeploy an existing image)
set -euo pipefail
GCLOUD=${GCLOUD:-gcloud}
PROJECT=nov21-gdp-hack; REGION=us-central1
IMAGE=us-central1-docker.pkg.dev/$PROJECT/sentineldesk/console
TAG=${TAG:-full}; MAX_KB=${MAX_KB:-0}
cd "$(dirname "$0")/../.."
if [ -z "${SKIP_BUILD:-}" ]; then
  # E2_HIGHCPU_32 is quota-blocked in us-central1 regional pools, so the build runs in the global pool.
  $GCLOUD builds submit --project $PROJECT --config cloudrun/console/cloudbuild.yaml \
    --ignore-file=cloudrun/console/.gcloudignore --substitutions=_MAX_KB=$MAX_KB,_TAG=$TAG .
fi
$GCLOUD run deploy sentineldesk-console --project $PROJECT --region $REGION \
  --image $IMAGE:$TAG --port 8080 --cpu 2 --memory 4Gi --min-instances 1 --max-instances 1 \
  --timeout 300 --session-affinity --no-cpu-throttling --allow-unauthenticated \
  --set-env-vars LLM_PROVIDER=none,HF_HUB_OFFLINE=1,TRANSFORMERS_OFFLINE=1,OMP_NUM_THREADS=2
# Switch on Gemini (OpenAI-compatible endpoint) later:
#   $GCLOUD run services update sentineldesk-console --project $PROJECT --region $REGION \
#     --set-secrets OPENAI_API_KEY=gemini-api-key:latest \
#     --update-env-vars "LLM_PROVIDER=openai,LLM_MODEL=gemini-flash-latest,OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/,LLM_TIMEOUT_S=20"
