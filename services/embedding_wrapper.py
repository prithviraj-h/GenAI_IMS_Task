#backend/services/embedding_wrapper.py
import requests
from core.config import settings
from typing import List
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self.api_key = settings.JINA_API_KEY
        self.model = settings.JINA_MODEL
        self.api_url = "https://api.jina.ai/v1/embeddings"
        
        if not self.api_key:
            logger.warning("⚠️ JINA_API_KEY not set. Embeddings will fail!")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Jina AI API"""
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json={
                    "model": self.model,
                    "input": [text]
                },
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract embedding from response
            embedding = data['data'][0]['embedding']
            logger.info(f"✅ Generated embedding (dim: {len(embedding)})")
            return embedding
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Jina API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Error generating embedding: {e}")
            return []
    
    def generate_query_embedding(self, text: str) -> List[float]:
        """Generate embedding for query (same as regular embedding for Jina)"""
        return self.generate_embedding(text)

# Global embedding service instance
embedding_service = EmbeddingService()