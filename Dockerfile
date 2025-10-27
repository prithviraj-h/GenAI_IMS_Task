# ---------- Stage 1: Builder ----------
    FROM python:3.12-slim AS builder

    WORKDIR /app
    
    # Install minimal build dependencies
    RUN apt-get update && \
        apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        && rm -rf /var/lib/apt/lists/* \
        && apt-get clean
    
    COPY requirements.txt .
    
    # Install with no cache and minimal disk usage
    RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
    
    # Clean up build dependencies to save space
    RUN apt-get remove -y gcc g++ && apt-get autoremove -y
    
    # Clean up Python cache
    RUN find /install -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
        find /install -name "*.pyc" -delete
    
    # ---------- Stage 2: Runtime ----------
    FROM python:3.12-slim
    
    WORKDIR /app
    
    # Install only essential runtime dependencies
    RUN apt-get update && \
        apt-get install -y --no-install-recommends \
        && rm -rf /var/lib/apt/lists/* \
        && apt-get clean
    
    COPY --from=builder /install /usr/local
    
    # Copy your application (keep all your existing code)
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
    
    # Single worker to save memory
    CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]