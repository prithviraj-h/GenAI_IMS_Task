from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging
import gc
import psutil

from core.config import settings
from db.mongo import mongo_client
from db.chroma import chroma_client
from services.kb_service import kb_service
from services.embedding_wrapper import embedding_service  # ✅ IMPORT embedding_service
from api import chat, admin
from api.incidents import router as incident_router

# ---------------- Memory Optimization ----------------
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
KB_FILE = os.path.join(BASE_DIR, "knowledge_base", "docs", "kb_data.txt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: handles startup/shutdown"""
    logger.info("🚀 Starting application...")
    
    try:
        # Force garbage collection before starting services
        gc.collect()
        
        # Connect to MongoDB
        logger.info("📡 Connecting to MongoDB...")
        mongo_client.connect()
        logger.info("✅ MongoDB connected successfully")
        
        # Connect to ChromaDB
        logger.info("📚 Connecting to ChromaDB...")
        chroma_client.connect()
        logger.info("✅ ChromaDB connected successfully")
        
        # Initialize Knowledge Base if not already populated
        if os.path.exists(KB_FILE):
            logger.info(f"📖 Checking KB file: {KB_FILE}")
            existing_entries = chroma_client.get_all_entries()
            logger.info(f"📊 Found {len(existing_entries)} existing KB entries in ChromaDB")
            
            if not existing_entries:
                logger.info("📘 KB empty - Initializing knowledge base...")
                success = kb_service.initialize_kb_from_file(KB_FILE)
                if success:
                    # Verify initialization
                    new_entries = chroma_client.get_all_entries()
                    logger.info(f"✅ Knowledge base initialized with {len(new_entries)} entries")
                else:
                    logger.error("❌ Failed to initialize knowledge base")
            else:
                logger.info(f"ℹ️  KB already initialized with {len(existing_entries)} entries:")
                for entry in existing_entries[:3]:  # Show first 3 entries
                    logger.info(f"   - {entry.get('id')}: {entry.get('metadata', {}).get('use_case', 'N/A')[:50]}")
        else:
            logger.warning(f"⚠️  KB file not found at: {KB_FILE}")
            logger.warning(f"⚠️  Current directory: {os.getcwd()}")
            logger.warning(f"⚠️  Files in knowledge_base/docs/:")
            kb_docs_dir = os.path.join(BASE_DIR, "knowledge_base", "docs")
            if os.path.exists(kb_docs_dir):
                logger.warning(f"    {os.listdir(kb_docs_dir)}")
        
        # ✅ FIX: Test embedding service correctly
        logger.info("🧪 Testing embedding service...")
        test_embedding = embedding_service.generate_embedding("test query")  # ✅ Use imported service
        if test_embedding:
            logger.info(f"✅ Embedding service working (dim: {len(test_embedding)})")
        else:
            logger.error("❌ Embedding service NOT working")
        
        logger.info("🎉 Application startup complete")
        
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR during startup: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    
    yield  # --- app runs here ---
    
    # Shutdown logic
    logger.info("🛑 Shutting down application...")
    mongo_client.disconnect()
    logger.info("✅ Application shutdown complete")


# ---------------- App Initialization ----------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(incident_router, prefix="/api", tags=["Incidents"])
app.include_router(admin.router)

# Mount static frontend
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------- Routes ----------------
@app.get("/", response_class=HTMLResponse)
async def root_page():
    """Serve main user interface"""
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h2>Frontend not found</h2>", status_code=404)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """Serve admin interface"""
    html_path = os.path.join(STATIC_DIR, "admin.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h2>Admin frontend not found</h2>", status_code=404)


# ✅ REMOVED: /health endpoint (as requested)


# Memory monitoring endpoint for debugging
@app.get("/api/memory-status")
async def memory_status():
    """Monitor memory usage (for debugging)"""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
            "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
            "available_memory_mb": round(psutil.virtual_memory().available / 1024 / 1024, 2),
            "memory_percent": round(psutil.virtual_memory().percent, 2),
            "optimized": True
        }
    except Exception as e:
        return {"error": str(e), "optimized": True}


# For local run only
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
