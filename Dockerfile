FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for chroma-hnswlib and SSL dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    gcc \
    ca-certificates \
    libssl3 \
    openssl \
    libgomp1 \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade certifi

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

# ✅ CRITICAL: Create kb_data.txt if it doesn't exist
RUN mkdir -p /app/knowledge_base/docs && \
    if [ ! -f /app/knowledge_base/docs/kb_data.txt ]; then \
        echo "# Knowledge Base Entries" > /app/knowledge_base/docs/kb_data.txt && \
        echo "# Last Updated: $(date)" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "# Total Entries: 4" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "==================================================" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "[KB_ID: 001]" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Use Case: Outlook Not Opening" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Required Info:" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Operating System" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Account Type" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Error Message" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Solution Steps:" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Verify internet connectivity" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Check Outlook version and apply latest updates" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Restart Outlook in Safe Mode" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "--------------------------------------------------" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "==================================================" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "[KB_ID: 002]" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Use Case: VPN Connection Failed" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Required Info:" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Operating System" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- VPN Client" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Network Type" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Error Message" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Solution Steps:" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Check internet connection" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Verify VPN credentials" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Restart VPN client" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "--------------------------------------------------" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "==================================================" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "[KB_ID: 003]" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Use Case: Password Reset Request" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Required Info:" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- User ID" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Email Address" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Solution Steps:" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Verify user identity" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Send password reset link via email" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Guide user through password reset process" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "--------------------------------------------------" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "==================================================" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "[KB_ID: 004]" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Use Case: Software Installation Request" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Required Info:" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Software Name" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Operating System" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Business Justification" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "Solution Steps:" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Verify software license availability" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Check system compatibility" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "- Schedule installation with user" >> /app/knowledge_base/docs/kb_data.txt && \
        echo "--------------------------------------------------" >> /app/knowledge_base/docs/kb_data.txt; \
    fi

# Verify the file was created
RUN ls -la /app/knowledge_base/docs/ && \
    echo "KB file contents:" && \
    head -20 /app/knowledge_base/docs/kb_data.txt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
