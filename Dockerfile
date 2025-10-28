FROM python:3.12-slim

WORKDIR /app

# Install SSL dependencies and CA certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    openssl \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure certifi is installed for SSL verification
RUN pip install --no-cache-dir --upgrade certifi

# Copy application code
COPY api ./api
COPY core ./core
COPY db ./db
COPY models ./models
COPY services ./services
COPY static ./static
COPY utils ./utils
COPY knowledge_base ./knowledge_base
COPY main.py ./

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
