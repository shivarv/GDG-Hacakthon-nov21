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
MODEL="${MODEL:-triage.joblib}"          # file served (triage.joblib or blend.joblib)
MODEL_KIND="${MODEL_KIND:-lr}"             # lr | blend
MODEL_DIR="${MODEL_DIR:-$REPO/triage/models}"  # where $MODEL (and triage.joblib) live locally
CPU="${CPU:-2}"; MEMORY="${MEMORY:-2Gi}"

BUILD="$HERE/.build"
rm -rf "$BUILD" && mkdir -p "$BUILD/triage/models"
cp "$HERE/app.py" "$HERE/rag.py" "$HERE/demo.html" "$HERE/requirements.txt" "$HERE/Dockerfile" "$BUILD/"
cp "$REPO/dataset/data/kb_train.parquet" "$BUILD/"  # 80% KB only, for retrieval
cp "$REPO/triage/model.py" "$REPO/triage/textprep.py" "$REPO/triage/urgency.py" "$REPO/triage/blend.py" "$BUILD/triage/"
cp "$MODEL_DIR/$MODEL" "$BUILD/triage/models/"
if [ "$MODEL_KIND" = blend ]; then cp "$MODEL_DIR/triage.joblib" "$BUILD/triage/models/"; fi  # BlendModel loads the LR beside it
printf '.gcloudignore\n__pycache__/\n' > "$BUILD/.gcloudignore"

gcloud run deploy "$SERVICE" \
  --project "$PROJECT" --region "$REGION" --source "$BUILD" \
  --cpu "$CPU" --memory "$MEMORY" --min-instances 1 --max-instances 3 --concurrency 8 \
  --no-cpu-throttling --cpu-boost --timeout 60 \
  --set-env-vars "MODEL_PATH=/app/triage/models/$MODEL,MODEL_KIND=$MODEL_KIND" \
  --startup-probe "tcpSocket.port=8080,periodSeconds=10,timeoutSeconds=5,failureThreshold=60" \
  --allow-unauthenticated --quiet
gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)'
