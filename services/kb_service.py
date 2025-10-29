# backend/services/kb_service.py
from db.chroma import chroma_client
from db.mongo import mongo_client
from services.embedding_wrapper import embedding_service
from utils.preprocessing import parse_kb_file
from typing import Dict, List, Any, Optional
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class KBService:
    def __init__(self):
        self.similarity_threshold = 0.35
        self.kb_file_path = self._get_kb_file_path()  # Initialize file path

    def _get_kb_file_path(self):
        """Get the correct path to kb_data.txt"""
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Try multiple possible locations
        possible_paths = [
            os.path.join(current_dir, "..", "knowledge_base", "docs", "kb_data.txt"),
            os.path.join(current_dir, "knowledge_base", "docs", "kb_data.txt"),
            "knowledge_base/docs/kb_data.txt",
            "../knowledge_base/docs/kb_data.txt",
            os.path.join(os.getcwd(), "knowledge_base", "docs", "kb_data.txt")
        ]
        
        for path in possible_paths:
            full_path = os.path.abspath(path)
            if os.path.exists(full_path):
                logger.info(f"Found KB file at: {full_path}")
                return full_path
        
        # If no file exists, create one in the most likely location
        default_path = os.path.join(current_dir, "..", "knowledge_base", "docs", "kb_data.txt")
        os.makedirs(os.path.dirname(default_path), exist_ok=True)
        logger.info(f"Using default KB file path: {default_path}")
        return default_path

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
        """Append new KB entry to kb_data.txt file with proper formatting"""
        try:
            logger.info(f"=== STARTING KB FILE APPEND ===")
            logger.info(f"KB ID: {kb_id}")
            logger.info(f"Use Case: {use_case}")
            logger.info(f"File Path: {self.kb_file_path}")
            
            if not self.kb_file_path:
                logger.error("❌ KB file path not set")
                return False
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.kb_file_path), exist_ok=True)
            logger.info(f"Directory ensured: {os.path.dirname(self.kb_file_path)}")
            
            # Check if file exists and read current content
            file_exists = os.path.exists(self.kb_file_path)
            current_content = ""
            
            if file_exists:
                with open(self.kb_file_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
                current_size = len(current_content)
                logger.info(f"📄 File exists, current size: {current_size} bytes")
            else:
                logger.info("📄 File does not exist, will create new file")
                # Create initial header for new file
                current_content = "# Knowledge Base Entries\n"
                current_content += f"# Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                current_content += "# Total Entries: 0\n\n"
            
            # Extract KB number from kb_id
            if kb_id.startswith('KB_'):
                kb_number = kb_id.split('_')[1]
            else:
                kb_number = kb_id[2:] if kb_id.startswith('KB') else kb_id
            
            # Format the new entry exactly like existing entries
            new_entry = f"\n{'='*50}\n"
            new_entry += f"[KB_ID: {kb_number}]\n\n"
            new_entry += f"Use Case: {use_case}\n\n"
            
            if required_info:
                new_entry += "Required Info:\n"
                for info in required_info:
                    new_entry += f"- {info}\n"
                new_entry += "\n"
            
            new_entry += "Solution Steps:\n"
            if isinstance(solution_steps, list):
                for step in solution_steps:
                    # Ensure each step starts with a bullet point
                    if not step.strip().startswith('-'):
                        new_entry += f"- {step}\n"
                    else:
                        new_entry += f"{step}\n"
            else:
                # If it's a string, split by newlines and format as bullets
                steps = solution_steps.split('\n')
                for step in steps:
                    step_clean = step.strip()
                    if step_clean and not step_clean.startswith('-'):
                        new_entry += f"- {step_clean}\n"
                    elif step_clean:
                        new_entry += f"{step_clean}\n"
            
            new_entry += f"{'-'*50}"
            
            logger.info(f"New entry length: {len(new_entry)} characters")
            
            # Append to file
            with open(self.kb_file_path, 'w', encoding='utf-8') as f:
                f.write(current_content + new_entry)
            
            # Verify the write
            new_size = os.path.getsize(self.kb_file_path)
            logger.info(f"✅ File write completed, new size: {new_size} bytes")
            
            # Update the header with new entry count
            self._update_kb_file_header()
            
            logger.info(f"=== KB FILE APPEND COMPLETED ===")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error appending to KB file: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _update_kb_file_header(self):
        """Update the KB file header with current entry count and timestamp"""
        try:
            if not os.path.exists(self.kb_file_path):
                return
            
            with open(self.kb_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Count KB entries
            entry_count = content.count('[KB_ID:')
            
            # Update header
            lines = content.split('\n')
            updated_lines = []
            
            for line in lines:
                if line.startswith('# Last Updated:'):
                    updated_lines.append(f"# Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                elif line.startswith('# Total Entries:'):
                    updated_lines.append(f"# Total Entries: {entry_count}")
                else:
                    updated_lines.append(line)
            
            # Write back with updated header
            with open(self.kb_file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(updated_lines))
                
            logger.info(f"✅ KB file header updated: {entry_count} entries")
            
        except Exception as e:
            logger.error(f"Error updating KB file header: {e}")
    
    def search_kb(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Search knowledge base for similar entries with improved matching"""
        try:
            logger.info(f"🔍 Searching KB for: '{query}'")
            
            query_embedding = embedding_service.generate_query_embedding(query)
            
            if not query_embedding:
                logger.error("❌ Failed to generate query embedding")
                return {"matches": [], "best_match": None}
            
            logger.info(f"✅ Generated query embedding (dim: {len(query_embedding)})")
            
            results = chroma_client.search_similar(query_embedding, n_results)
            
            matches = []
            best_match = None
            highest_similarity = 0
            
            if results and results['ids'] and results['ids'][0]:
                logger.info(f"📊 Found {len(results['ids'][0])} potential matches")
                
                for i in range(len(results['ids'][0])):
                    kb_id = results['ids'][0][i]
                    distance = results['distances'][0][i]
                    metadata = results['metadatas'][0][i]
                    document = results['documents'][0][i]
                    
                    similarity = 1 - distance
                    
                    # Calculate additional similarity factors
                    use_case = metadata.get('use_case', '').lower()
                    query_lower = query.lower()
                    
                    # Keyword overlap bonus
                    use_case_words = set(use_case.split())
                    query_words = set(query_lower.split())
                    keyword_overlap = len(use_case_words.intersection(query_words)) / len(use_case_words.union(query_words)) if use_case_words.union(query_words) else 0
                    
                    # Enhanced similarity with keyword bonus
                    enhanced_similarity = similarity + (keyword_overlap * 0.3)  # ✅ INCREASED bonus
                    enhanced_similarity = min(enhanced_similarity, 1.0)
                    
                    logger.info(f"🎯 {kb_id}: Base={similarity:.3f}, Enhanced={enhanced_similarity:.3f}, Keywords={keyword_overlap:.3f}, Use Case: {use_case[:50]}")
                    
                    match_data = {
                        'kb_id': kb_id,
                        'similarity': similarity,
                        'enhanced_similarity': enhanced_similarity,
                        'use_case': metadata.get('use_case', ''),
                        'required_info': metadata.get('required_info', '').split(','),
                        'questions': metadata.get('questions', '').split(','),
                        'solution_steps': metadata.get('solution_steps', ''),
                        'full_text': document
                    }
                    
                    matches.append(match_data)
                    
                    if enhanced_similarity > highest_similarity:
                        highest_similarity = enhanced_similarity
                        best_match = match_data
            
            # ✅ CHANGED: Dynamic threshold adjustment
            dynamic_threshold = max(0.25, self.similarity_threshold - 0.1)  # Lower minimum to 0.25
            
            if best_match and best_match['enhanced_similarity'] >= dynamic_threshold:
                logger.info(f"✅ MATCH FOUND: {best_match['kb_id']} with similarity {best_match['enhanced_similarity']:.3f} (threshold: {dynamic_threshold:.3f})")
            else:
                logger.warning(f"❌ NO MATCH: Best similarity {highest_similarity:.3f} below threshold {dynamic_threshold:.3f}")
                best_match = None
            
            return {
                "matches": matches,
                "best_match": best_match,
                "highest_enhanced_similarity": highest_similarity
            }
            
        except Exception as e:
            logger.error(f"❌ Error searching KB: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"matches": [], "best_match": None, "highest_enhanced_similarity": 0}
    
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