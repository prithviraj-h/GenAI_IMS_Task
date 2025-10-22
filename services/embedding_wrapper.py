#backend/services/embedding_wrapper.py
from sentence_transformers import SentenceTransformer
from core.config import settings
from typing import List
import logging

logger = logging.getLogger(__name__)



class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')  
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Gemini"""
        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []
    
    def generate_query_embedding(self, text: str) -> List[float]:
        """Generate embedding for query using Gemini"""
        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            return []


# Global embedding service instance
embedding_service = EmbeddingService()