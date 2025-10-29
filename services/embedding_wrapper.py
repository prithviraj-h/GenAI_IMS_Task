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
    
    # services/embedding_wrapper.py - REPLACE the generate_embedding method

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Jina AI API with retries"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Attempt {attempt + 1}/{max_retries}: Generating embedding for: '{text[:50]}...'")
                
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
                if 'data' in data and len(data['data']) > 0 and 'embedding' in data['data'][0]:
                    embedding = data['data'][0]['embedding']
                    logger.info(f"✅ Generated embedding successfully (dim: {len(embedding)})")
                    return embedding
                else:
                    logger.error(f"❌ Invalid response format: {data}")
                    if attempt < max_retries - 1:
                        continue
                    return []
                
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Jina API request failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)  # Wait 1 second before retry
                    continue
                return []
            except Exception as e:
                logger.error(f"❌ Error generating embedding (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    continue
                return []
        
        logger.error(f"❌ Failed to generate embedding after {max_retries} attempts")
        return []
    
    def generate_query_embedding(self, text: str) -> List[float]:
        """Generate embedding for query (same as regular embedding for Jina)"""
        return self.generate_embedding(text)

# Global embedding service instance
embedding_service = EmbeddingService()