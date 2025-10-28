#backend/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # MongoDB Configuration
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    MONGO_DB: str = os.getenv("MONGO_DB", "incident_management")
    INCIDENT_COLLECTION: str = os.getenv("INCIDENT_COLLECTION", "incidents")
    SESSION_COLLECTION: str = os.getenv("SESSION_COLLECTION", "sessions")
    KB_COLLECTION: str = os.getenv("KB_COLLECTION", "kb_entries")
    # SSL/TLS settings for MongoDB Atlas
    MONGO_TLS: bool = True
    MONGO_TLS_ALLOW_INVALID_CERTIFICATES: bool = False
    # Gemini Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Embedding settings
    # EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    # EMBEDDING_DIMENSION: int = 128
    # Jina AI Embeddings Configuration
    JINA_API_KEY: str = os.getenv("JINA_API_KEY", "jina_f150959bc77a423a91d8f0e06c67fed54c5gR4NOpBdi88LOeUR6sNAhg-1_")
    JINA_MODEL: str = "jina-embeddings-v2-base-en"
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