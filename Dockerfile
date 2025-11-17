# === STAGE 1: Builder ===
FROM python:3.12 AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential g++ gcc libgomp1 ca-certificates libssl3 openssl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade certifi

# === STAGE 2: Runtime ===
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/

COPY api ./api
COPY core ./core
COPY db ./db
COPY models ./models
COPY services ./services
COPY static ./static
COPY utils ./utils
COPY knowledge_base ./knowledge_base
COPY main.py ./

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates libgomp1 && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Ensure KB file exists
RUN mkdir -p /app/knowledge_base/docs && \
    if [ ! -f /app/knowledge_base/docs/kb_data.txt ]; then \
        echo "# Default KB entries" > /app/knowledge_base/docs/kb_data.txt; \
    fi

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
