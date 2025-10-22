#backend/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # MongoDB Configuration
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB: str = os.getenv("MONGO_DB", "incident_management")
    INCIDENT_COLLECTION: str = os.getenv("INCIDENT_COLLECTION", "incidents")
    SESSION_COLLECTION: str = os.getenv("SESSION_COLLECTION", "sessions")
    KB_COLLECTION: str = os.getenv("KB_COLLECTION", "kb_entries")
    
    # Gemini Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Embedding settings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    
    # LLM settings
    LLM_MODEL: str = "gemini-2.0-flash"
    
    # ChromaDB Configuration - Support both field names
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./db/chroma")
    CHROMA_DIR: str = os.getenv("CHROMA_DIR", "./db/chroma")  # For compatibility
    
    # Application Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "GenAI Incident Management")
    PROJECT_VERSION: str = os.getenv("PROJECT_VERSION", "1.0.0")
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore any other extra fields


# Global settings instance
settings = Settings()