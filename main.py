# backend/main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
from core.config import settings
from db.mongo import mongo_client
from db.chroma import chroma_client
from services.kb_service import kb_service
from api import chat, admin
from api.incidents import router as incident_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events
    """
    # Startup
    logger.info("Starting up application...")
    try:
        # Connect to MongoDB
        mongo_client.connect()
        logger.info("MongoDB connected")
        
        # Connect to ChromaDB
        chroma_client.connect()
        logger.info("ChromaDB connected")
        
        # Initialize KB from file
        kb_file_path = os.path.join(os.path.dirname(__file__), "knowledge_base", "docs", "kb_data.txt")
        if os.path.exists(kb_file_path):
            # Check if KB is already initialized
            existing_entries = chroma_client.get_all_entries()
            if not existing_entries:
                logger.info("Initializing knowledge base...")
                kb_service.initialize_kb_from_file(kb_file_path)
                logger.info("Knowledge base initialized")
            else:
                logger.info(f"Knowledge base already has {len(existing_entries)} entries")
        else:
            logger.warning(f"KB file not found at: {kb_file_path}")
        
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    mongo_client.disconnect()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(incident_router, prefix="/api", tags=["incidents"])
app.include_router(admin.router)

# Create static directory if it doesn't exist
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Serve the main user interface
    """
    html_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    else:
        return HTMLResponse(content="<h1>Welcome to GenAI Incident Management System</h1><p>Frontend files not found. Please add index.html to the static directory.</p>")


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """
    Serve the admin interface
    """
    html_file = os.path.join(os.path.dirname(__file__), "static", "admin.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    else:
        return HTMLResponse(content="<h1>Admin Panel</h1><p>Admin page not found. Please add admin.html to the static directory.</p>")


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "version": settings.PROJECT_VERSION}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)