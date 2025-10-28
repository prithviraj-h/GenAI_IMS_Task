FROM python:3.12-slim

WORKDIR /app

# Install build dependencies (keep them during pip install)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NOW remove build dependencies to save space
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