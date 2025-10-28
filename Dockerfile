FROM python:3.12-slim

WORKDIR /app

# Install comprehensive SSL and build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    ca-certificates \
    libssl-dev \
    curl \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional Python SSL packages
RUN pip install --no-cache-dir pyopenssl cryptography

# Remove build dependencies but keep SSL packages
RUN apt-get remove -y gcc g++ && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

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
    PORT=8000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]