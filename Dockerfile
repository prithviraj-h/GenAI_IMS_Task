# -------------------------------
# 1️⃣ Base Image
# -------------------------------
    FROM python:3.12-slim

    # -------------------------------
    # 2️⃣ Set Work Directory
    # -------------------------------
    WORKDIR /app
    
    # -------------------------------
    # 3️⃣ Install system dependencies (C++ build tools)
    # -------------------------------
    RUN apt-get update && apt-get install -y \
        g++ \
        gcc \
        cmake \
        make \
        && rm -rf /var/lib/apt/lists/*
    
    # -------------------------------
    # 4️⃣ Copy dependency files
    # -------------------------------
    COPY requirements.txt .
    
    # -------------------------------
    # 5️⃣ Install Python dependencies
    # -------------------------------
    RUN pip install --upgrade pip \
        && pip install --no-cache-dir -r requirements.txt
    
    # -------------------------------
    # 6️⃣ Copy app source
    # -------------------------------
    COPY . .
    
    # -------------------------------
    # 7️⃣ Expose Port
    # -------------------------------
    EXPOSE 8000
    
    # -------------------------------
    # 8️⃣ Run the FastAPI app
    # -------------------------------
    CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
    