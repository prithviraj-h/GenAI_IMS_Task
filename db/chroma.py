#backend/db/chroma.py
import chromadb
from chromadb.config import Settings as ChromaSettings
from core.config import settings
from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class ChromaDBClient:
    def __init__(self):
        self.client = None
        self.collection = None
        
    def connect(self):
        """Initialize ChromaDB client"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(settings.CHROMA_DIR, exist_ok=True)
            
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_DIR,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name="kb_knowledge_base",
                metadata={"description": "Knowledge base for incident management"}
            )
            
            logger.info("Connected to ChromaDB successfully")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            raise
    
    def add_kb_entry(self, kb_id: str, text: str, embedding: List[float], metadata: Dict[str, Any]):
        """Add a knowledge base entry"""
        try:
            self.collection.add(
                ids=[kb_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata]
            )
            logger.info(f"Added KB entry: {kb_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding KB entry: {e}")
            return False
    
    def search_similar(self, query_embedding: List[float], n_results: int = 3) -> Dict[str, Any]:
        """Search for similar entries"""
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error(f"Error searching ChromaDB: {e}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    
    def get_entry_by_id(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """Get entry by KB ID"""
        try:
            results = self.collection.get(ids=[kb_id])
            if results and results['ids']:
                return {
                    'id': results['ids'][0],
                    'document': results['documents'][0],
                    'metadata': results['metadatas'][0]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting KB entry: {e}")
            return None
    
    def update_entry(self, kb_id: str, text: str, embedding: List[float], metadata: Dict[str, Any]):
        """Update an existing KB entry"""
        try:
            self.collection.update(
                ids=[kb_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata]
            )
            logger.info(f"Updated KB entry: {kb_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating KB entry: {e}")
            return False
    
    def delete_entry(self, kb_id: str):
        """Delete a KB entry"""
        try:
            self.collection.delete(ids=[kb_id])
            logger.info(f"Deleted KB entry: {kb_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting KB entry: {e}")
            return False
    
    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Get all KB entries"""
        try:
            results = self.collection.get()
            entries = []
            if results and results['ids']:
                for i in range(len(results['ids'])):
                    entries.append({
                        'id': results['ids'][i],
                        'document': results['documents'][i],
                        'metadata': results['metadatas'][i]
                    })
            return entries
        except Exception as e:
            logger.error(f"Error getting all KB entries: {e}")
            return []


# Global ChromaDB client instance
chroma_client = ChromaDBClient()