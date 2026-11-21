# Build context is the staging dir created by deploy/deploy.sh (app.py + triage/*.py + triage/models/).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY triage/ triage/
COPY app.py rag.py demo.html kb_train.parquet ./
EXPOSE 8080
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --timeout-keep-alive 75
