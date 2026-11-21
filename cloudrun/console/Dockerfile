# SentinelDesk Streamlit console for Cloud Run.
# Build context = repo root:  docker build -f cloudrun/console/Dockerfile .
# Artifacts (classifier + FAISS index) are built inside the image by scripts/build.py
# (leakage-safe split unchanged); the holdout parquet is deleted from the image afterwards.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/hf ARTIFACTS_DIR=/app/artifacts LLM_PROVIDER=none
WORKDIR /app
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ src/
COPY scripts/ scripts/
ARG MAX_KB=0
RUN python scripts/build.py --max-kb ${MAX_KB} \
 && rm -f artifacts/test_holdout.parquet \
 && rm -rf /app/hf/datasets \
 && ls -la artifacts artifacts/index
COPY app.py .
COPY cloudrun/console/streamlit_config.toml /app/.streamlit/config.toml
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
EXPOSE 8080
CMD exec streamlit run app.py --server.port ${PORT:-8080} --server.address 0.0.0.0 \
    --server.headless true --browser.gatherUsageStats false
