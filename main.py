# backend/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging

from core.config import settings
from db.mongo import mongo_client
from db.chroma import chroma_client
from services.kb_service import kb_service
from api import chat, admin
from api.incidents import router as incident_router

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
        # Connect to MongoDB
        mongo_client.connect()
        logger.info("✅ MongoDB connected")

        # Connect to ChromaDB
        chroma_client.connect()
        logger.info("✅ ChromaDB connected")

        # Initialize Knowledge Base if not already populated
        if os.path.exists(KB_FILE):
            existing_entries = chroma_client.get_all_entries()
            if not existing_entries:
                logger.info("📘 Initializing knowledge base...")
                kb_service.initialize_kb_from_file(KB_FILE)
                logger.info("✅ Knowledge base initialized")
            else:
                logger.info(f"ℹ️ KB already has {len(existing_entries)} entries")
        else:
            logger.warning(f"⚠️ KB file not found at: {KB_FILE}")

    except Exception as e:
        logger.error(f"❌ Error during startup: {e}")
        raise

    yield  # --- app runs here ---

    # Shutdown logic
    mongo_client.disconnect()
    logger.info("🛑 Application shutdown complete.")


# ---------------- App Initialization ----------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # can restrict later if needed
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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": settings.PROJECT_VERSION}


# For local run only
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
