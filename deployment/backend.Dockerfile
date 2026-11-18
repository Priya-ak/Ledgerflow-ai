# FastAPI backend with Tesseract OCR. Used by Render (render.yaml) and CI.
# Docker is NOT required for local development.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
# Files that pass through a Windows checkout can gain CRLF line endings and lose the executable bit.
# Normalise the line endings here and start the script through sh, so neither can stop the container.
RUN sed -i 's/\r$//' docker-entrypoint.sh
# Synthetic demo documents for SEED_DEMO_ON_START (seed.py resolves /sample-data).
COPY sample-data/synthetic-invoices /sample-data/synthetic-invoices

RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/storage && chown -R appuser /app
USER appuser

ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health',timeout=4)"
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
