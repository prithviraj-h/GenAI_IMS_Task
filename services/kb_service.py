# backend/services/kb_service.py
from db.chroma import chroma_client
from db.mongo import mongo_client
from services.embedding_wrapper import embedding_service
from utils.preprocessing import parse_kb_file
from typing import Dict, List, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)

class KBService:
    def __init__(self):
        self.similarity_threshold = 0.65  # Lowered from 0.7 to catch more similar issues
        self.kb_file_path = None
    
    def initialize_kb_from_file(self, file_path: str) -> bool:
        """Load knowledge base from file and store in ChromaDB"""
        try:
            self.kb_file_path = file_path
            
            if not os.path.exists(file_path):
                logger.error(f"KB file not found: {file_path}")
                return False
            
            kb_entries = parse_kb_file(file_path)
            
            if not kb_entries:
                logger.warning("No KB entries found in file")
                return False
            
            for entry in kb_entries:
                embedding = embedding_service.generate_embedding(entry['use_case'])
                
                if embedding:
                    metadata = {
                        'use_case': entry['use_case'],
                        'required_info': ','.join(entry['required_info']),
                        'questions': ','.join(entry['questions']),
                        'solution_steps': entry['solution_steps']
                    }
                    
                    chroma_client.add_kb_entry(
                        kb_id=entry['kb_id'],
                        text=entry['full_text'],
                        embedding=embedding,
                        metadata=metadata
                    )
                    
                    logger.info(f"Added KB entry: {entry['kb_id']}")
            
            logger.info(f"Successfully initialized KB with {len(kb_entries)} entries")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing KB: {e}")
            return False
    
    def append_to_kb_file(self, kb_id: str, use_case: str, required_info: List[str], solution_steps: List[str]):
        """Append new KB entry to kb_data.txt file"""
        try:
            if not self.kb_file_path:
                logger.error("KB file path not set")
                return False
            
            # Extract KB number from kb_id (e.g., KB_5 -> 5)
            kb_number = kb_id.split('_')[1]
            
            # Format the entry
            entry_text = f"\n\n{'='*50}\n"
            entry_text += f"[KB_ID: {kb_number}]\n\n"
            entry_text += f"Use Case: {use_case}\n\n"
            entry_text += "Required Info:\n"
            for info in required_info:
                entry_text += f"- {info}\n"
            entry_text += "\n"
            entry_text += "Solution Steps:\n"
            if isinstance(solution_steps, list):
                for step in solution_steps:
                    entry_text += f"{step}\n"
            else:
                entry_text += f"{solution_steps}\n"
            entry_text += f"\n{'-'*50}"
            
            # Append to file
            with open(self.kb_file_path, 'a', encoding='utf-8') as f:
                f.write(entry_text)
            
            logger.info(f"Appended KB entry {kb_id} to file: {self.kb_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error appending to KB file: {e}")
            return False
    
    def search_kb(self, query: str, n_results: int = 3) -> Dict[str, Any]:
        """Search knowledge base for similar entries"""
        try:
            query_embedding = embedding_service.generate_query_embedding(query)
            
            if not query_embedding:
                return {"matches": [], "best_match": None}
            
            results = chroma_client.search_similar(query_embedding, n_results)
            
            matches = []
            best_match = None
            
            if results and results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    kb_id = results['ids'][0][i]
                    distance = results['distances'][0][i]
                    metadata = results['metadatas'][0][i]
                    document = results['documents'][0][i]
                    
                    similarity = 1 - distance
                    
                    logger.info(f"KB Match: {kb_id} - {metadata.get('use_case', '')} - Similarity: {similarity:.3f}")
                    
                    match_data = {
                        'kb_id': kb_id,
                        'similarity': similarity,
                        'use_case': metadata.get('use_case', ''),
                        'required_info': metadata.get('required_info', '').split(','),
                        'questions': metadata.get('questions', '').split(','),
                        'solution_steps': metadata.get('solution_steps', ''),
                        'full_text': document
                    }
                    
                    matches.append(match_data)
                    
                    if similarity >= self.similarity_threshold and best_match is None:
                        best_match = match_data
                        logger.info(f"✅ Best KB match found: {kb_id} with similarity {similarity:.3f}")
            
            if not best_match:
                logger.info(f"❌ No KB match found above threshold {self.similarity_threshold}")
            
            return {
                "matches": matches,
                "best_match": best_match
            }
            
        except Exception as e:
            logger.error(f"Error searching KB: {e}")
            return {"matches": [], "best_match": None}
    
    def get_kb_entry(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """Get specific KB entry by ID"""
        try:
            entry = chroma_client.get_entry_by_id(kb_id)
            
            if entry:
                metadata = entry['metadata']
                return {
                    'kb_id': kb_id,
                    'use_case': metadata.get('use_case', ''),
                    'required_info': metadata.get('required_info', '').split(','),
                    'questions': metadata.get('questions', '').split(','),
                    'solution_steps': metadata.get('solution_steps', ''),
                    'full_text': entry['document']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting KB entry: {e}")
            return None
    
    def add_new_kb_entry(self, use_case: str, required_info: List[str],
                        solution_steps: str, questions: List[str] = None) -> Optional[str]:
        """Add a new KB entry (for approved incidents)"""
        try:
            all_entries = chroma_client.get_all_entries()
            max_id = 0
            for entry in all_entries:
                kb_id = entry['id']
                if kb_id.startswith('KB_'):
                    try:
                        num = int(kb_id.split('_')[1])
                        max_id = max(max_id, num)
                    except:
                        pass
            
            new_kb_id = f"KB_{max_id + 1}"
            
            # Handle solution_steps if it's a list
            if isinstance(solution_steps, list):
                solution_text = "\n".join(solution_steps)
            else:
                solution_text = solution_steps
            
            full_text = f"Use Case: {use_case}\nRequired Info: {', '.join(required_info)}\nSolution Steps: {solution_text}"
            
            embedding = embedding_service.generate_embedding(use_case)
            
            if not embedding:
                logger.error("Failed to generate embedding for new KB entry")
                return None
            
            # Generate questions if not provided
            if not questions:
                questions = []
                for info in required_info:
                    info_lower = info.lower()
                    if 'operating system' in info_lower or 'os' in info_lower:
                        questions.append("What operating system are you using?")
                    elif 'error message' in info_lower or 'error code' in info_lower:
                        questions.append("Are you seeing any error messages? If yes, what does it say?")
                    elif 'account type' in info_lower:
                        questions.append("What type of account is this?")
                    elif 'device' in info_lower:
                        questions.append("What is your device name or ID?")
                    else:
                        questions.append(f"Can you provide information about: {info}?")
            
            metadata = {
                'use_case': use_case,
                'required_info': ','.join(required_info),
                'questions': ','.join(questions),
                'solution_steps': solution_text
            }
            
            success = chroma_client.add_kb_entry(new_kb_id, full_text, embedding, metadata)
            
            if success:
                logger.info(f"Added new KB entry: {new_kb_id}")
                return new_kb_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error adding new KB entry: {e}")
            return None
    
    def update_kb_entry(self, kb_id: str, solution_steps: str) -> bool:
        """Update solution steps for a KB entry"""
        try:
            entry = self.get_kb_entry(kb_id)
            
            if not entry:
                logger.error(f"KB entry not found: {kb_id}")
                return False
            
            entry['solution_steps'] = solution_steps
            
            full_text = f"Use Case: {entry['use_case']}\nRequired Info: {', '.join(entry['required_info'])}\nSolution Steps: {solution_steps}"
            
            embedding = embedding_service.generate_embedding(entry['use_case'])
            
            if not embedding:
                logger.error("Failed to generate embedding for updated KB entry")
                return False
            
            metadata = {
                'use_case': entry['use_case'],
                'required_info': ','.join(entry['required_info']),
                'questions': ','.join(entry['questions']),
                'solution_steps': solution_steps
            }
            
            success = chroma_client.update_entry(kb_id, full_text, embedding, metadata)
            
            if success:
                logger.info(f"Updated KB entry: {kb_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating KB entry: {e}")
            return False

# Global KB service instance
kb_service = KBService()