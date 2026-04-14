FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY sensory_cortex.py .
COPY myelination.py .
COPY brain_health.py .
COPY ingest.py .
COPY ingest_persistence.py .
COPY ingest_models.py .
COPY ingest_sanitize.py .
COPY ingest_filter.py .
COPY ingest_dedupe.py .
COPY ingest_rate_limit.py .
COPY classifier.py .
COPY auto_linker.py .

EXPOSE 8050

CMD ["python", "server.py"]
