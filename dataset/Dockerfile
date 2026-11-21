FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 HF_HOME=/models
WORKDIR /app

# CPU-only torch keeps the image small (no CUDA libraries).
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements-embed.txt .
RUN pip install -r requirements-embed.txt

# Bake the model into the image so tasks never download from Hugging Face at run time.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"
ENV HF_HUB_OFFLINE=1

COPY embed.py .
CMD ["python", "embed.py"]
