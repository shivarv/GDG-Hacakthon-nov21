#!/usr/bin/env bash
# Deploy HelpDesk (backend + frontend) to Cloud Run. Run from anywhere.
# Backend: SQLite inside the container (data resets on restart), single instance.
set -euo pipefail
GCLOUD=${GCLOUD:-gcloud}
PROJECT=${PROJECT:-nov21-gdp-hack}
REGION=${REGION:-us-central1}
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ "${1:-all}" != "frontend" ]]; then
  "$GCLOUD" run deploy helpdesk-backend --source "$ROOT/backend" \
    --project "$PROJECT" --region "$REGION" --port 8000 --allow-unauthenticated \
    --min-instances 1 --max-instances 1 --no-cpu-throttling --memory 1Gi --cpu 1 \
    --set-env-vars "DATABASE_URL=sqlite:///./.data/helpdesk.db,CORS_ORIGINS=*,EMAIL_LISTENER_ENABLED=false,SMTP_ENABLED=false,TEMP_INBOX_ENABLED=true,AUTO_ESCALATE=true,TRIAGE_MODEL=sentinel,ETA_MODEL=dummy,SUPPORT_TIMEZONE=America/New_York" \
    --quiet
fi

BACKEND_URL=$("$GCLOUD" run services describe helpdesk-backend --project "$PROJECT" --region "$REGION" --format 'value(status.url)')

# Build context = frontend/ sources + the Cloud Run Dockerfile and nginx template.
CTX=$(mktemp -d)
trap 'rm -rf "$CTX"' EXIT
rsync -a --exclude node_modules --exclude dist "$ROOT/frontend/" "$CTX/"
cp "$ROOT/cloudrun/helpdesk/frontend/Dockerfile" "$ROOT/cloudrun/helpdesk/frontend/cloudrun.nginx.conf.template" "$CTX/"

"$GCLOUD" run deploy helpdesk-frontend --source "$CTX" \
  --project "$PROJECT" --region "$REGION" --port 8080 --allow-unauthenticated \
  --min-instances 1 --set-env-vars "BACKEND_URL=$BACKEND_URL" --quiet
