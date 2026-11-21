#!/usr/bin/env bash
# Run from Cloud Shell inside this folder. Each block can be pasted on its own.
set -euo pipefail

export PROJECT=$(gcloud config get-value project)
export REGION=us-central1
export BUCKET=${PROJECT}-sentinel
gcloud config set run/region "$REGION"

# --- 0. One-time setup (skip any step that says "already exists") ---
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com storage.googleapis.com
gcloud storage buckets create "gs://$BUCKET" --location="$REGION" || true
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
# Cloud Run jobs run as the default compute service account; let it read/write the bucket.
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role=roles/storage.objectAdmin

# --- 1. Clean split (runs in Cloud Shell, ~5-8 min: near-copy check). Or upload a local data/ ---
pip install --user -q datasets pandas pyarrow numpy scikit-learn
python3 split.py
gcloud storage cp data/*.parquet data/split_meta.json "gs://$BUCKET/data-clean/"

# --- 2. Embed (Cloud Run job: 10 parallel CPU tasks, no GPU quota needed) ---
gcloud run jobs deploy embed-clean --source . \
  --tasks 10 --parallelism 10 --cpu 4 --memory 8Gi \
  --task-timeout 60m --max-retries 1 \
  --set-env-vars "BUCKET=$BUCKET,THREADS=4,DATA_PREFIX=data-clean,OUT_PREFIX=emb-clean/e5-small"
gcloud run jobs execute embed-clean --wait

# --- 3. Merge + twin check (Cloud Shell) ---
mkdir -p emb_shards
gcloud storage cp "gs://$BUCKET/emb-clean/e5-small/shard_*" emb_shards/
python3 merge.py --shards emb_shards --data data --out emb
gcloud storage cp emb/* "gs://$BUCKET/emb-clean/e5-small/merged/"

echo "Done. Teammates load: gs://$BUCKET/emb-clean/e5-small/merged/{kb_emb.npy,kb_ids.parquet}"
