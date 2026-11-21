#!/usr/bin/env bash
# Stage a clean build context and deploy the triage service to Cloud Run (CPU only, us-central1).
#   usage: PROJECT=<gcp-project-id> deploy/deploy.sh
# triage/*.py are copied unchanged (not edited); the model is baked into the image.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
PROJECT="${PROJECT:?set PROJECT=<gcp project id>}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-sentinel-triage}"
MODEL="${MODEL:-triage.joblib}"

BUILD="$HERE/.build"
rm -rf "$BUILD" && mkdir -p "$BUILD/triage/models"
cp "$HERE/app.py" "$HERE/requirements.txt" "$HERE/Dockerfile" "$BUILD/"
cp "$REPO/triage/model.py" "$REPO/triage/textprep.py" "$REPO/triage/urgency.py" "$BUILD/triage/"
cp "$REPO/triage/models/$MODEL" "$BUILD/triage/models/"
printf '.gcloudignore\n__pycache__/\n' > "$BUILD/.gcloudignore"

gcloud run deploy "$SERVICE" \
  --project "$PROJECT" --region "$REGION" --source "$BUILD" \
  --cpu 2 --memory 2Gi --min-instances 1 --max-instances 3 --concurrency 8 \
  --no-cpu-throttling --cpu-boost --timeout 60 \
  --set-env-vars "MODEL_PATH=/app/triage/models/$MODEL" \
  --allow-unauthenticated --quiet
gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)'
