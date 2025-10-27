# ---------- Stage 1: Builder ----------
    FROM python:3.12-slim AS builder
    WORKDIR /app
    
    # Install build dependencies for ChromaDB (needs g++ for chroma-hnswlib)
    RUN apt-get update && \
        apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        && rm -rf /var/lib/apt/lists/*
    
    COPY requirements.txt .
    RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
    
    # Clean up test files and cache (SAFE - doesn't affect functionality)
    RUN find /install -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
        find /install -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
        find /install -name "*.pyc" -delete
    
    # ---------- Stage 2: Runtime ----------
    FROM python:3.12-slim
    WORKDIR /app
    
    COPY --from=builder /install /usr/local
    
    # Copy your application
    COPY api ./api
    COPY core ./core
    COPY db ./db
    COPY knowledge_base ./knowledge_base
    COPY models ./models
    COPY services ./services
    COPY static ./static
    COPY utils ./utils
    COPY main.py __init__.py ./
    
    ENV PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1 \
        PORT=8000
    
    EXPOSE 8000
    CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]