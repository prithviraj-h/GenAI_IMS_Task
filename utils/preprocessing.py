#backend/utils/preprocessing.py
import re
import uuid
import json
from typing import Dict, List, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def generate_incident_id() -> str:
    """Generate unique incident ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"INC{timestamp}"


def generate_kb_id() -> str:
    """Generate unique KB ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:4]
    return f"KB{timestamp}{random_suffix}"


def extract_json_from_response(response: str) -> Dict[str, Any]:
    """Extract JSON from LLM response"""
    try:
        # Find JSON in the response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_str = response[json_start:json_end]
            return json.loads(json_str)
        
        return {}
    except Exception as e:
        logger.error(f"Error extracting JSON from response: {e}")
        return {}


def parse_kb_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse knowledge base file and extract structured data
    
    Expected format:
    ----------------------------------------------
    [KB_ID: 1]
    Use Case: Outlook Not Opening
    Required Info:
      - Operating System (Windows/Mac/Linux)
      - Account Type (Office365/Exchange/IMAP)
      - Error Message (if any)
    Solution Steps:
      - Verify internet connectivity.
      - Check Outlook version and apply latest updates.
    --------------------------------------------------
    """
    entries = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Split by entry separators (multiple dashes)
        raw_entries = re.split(r'-{40,}', content)
        
        for raw_entry in raw_entries:
            entry = _parse_single_entry(raw_entry.strip())
            if entry:
                entries.append(entry)
        
        logger.info(f"Parsed {len(entries)} KB entries from {file_path}")
        
    except Exception as e:
        logger.error(f"Error parsing KB file {file_path}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return entries


def _parse_single_entry(entry_text: str) -> Dict[str, Any]:
    """Parse a single KB entry from the new format"""
    if not entry_text.strip():
        return None
    
    lines = entry_text.strip().split('\n')
    entry = {
        'kb_id': '',
        'use_case': '',
        'required_info': [],
        'questions': [],
        'solution_steps': '',
        'full_text': entry_text
    }
    
    current_section = None
    temp_buffer = []
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # Check for KB_ID
        if line_stripped.startswith('[KB_ID:'):
            match = re.search(r'\[KB_ID:\s*(\d+)\]', line_stripped)
            if match:
                entry['kb_id'] = f"KB_{match.group(1).zfill(3)}"
        
        # Check for Use Case
        elif line_stripped.startswith('Use Case:'):
            entry['use_case'] = line_stripped.replace('Use Case:', '').strip()
            current_section = None
        
        # Check for Required Info section
        elif line_stripped.startswith('Required Info:'):
            current_section = 'required_info'
            temp_buffer = []
        
        # Check for Solution Steps section
        elif line_stripped.startswith('Solution Steps:'):
            # Save required info before switching sections
            if current_section == 'required_info' and temp_buffer:
                entry['required_info'] = temp_buffer.copy()
            
            current_section = 'solution_steps'
            temp_buffer = []
        
        # Parse bullet points
        elif line_stripped.startswith('-'):
            content = line_stripped[1:].strip()
            if current_section == 'required_info':
                # Clean up the required info (remove parentheses content)
                clean_content = re.sub(r'\s*\([^)]*\)', '', content)
                temp_buffer.append(clean_content.strip())
            elif current_section == 'solution_steps':
                temp_buffer.append(content)
    
    # Save remaining buffer
    if current_section == 'required_info' and temp_buffer:
        entry['required_info'] = temp_buffer
    elif current_section == 'solution_steps' and temp_buffer:
        entry['solution_steps'] = '\n'.join(temp_buffer)
    
    # Generate questions from required info
    if entry['required_info']:
        entry['questions'] = [f"Can you please provide: {info}?" for info in entry['required_info']]
    
    # Validate required fields
    if not all([entry['kb_id'], entry['use_case'], entry['required_info']]):
        logger.warning(f"Skipping incomplete KB entry: {entry.get('kb_id', 'Unknown')}")
        return None
    
    logger.info(f"Successfully parsed KB entry: {entry['kb_id']} - {entry['use_case']}")
    
    return entry


def clean_text(text: str) -> str:
    """Clean and normalize text for processing"""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s.,!?;:]', '', text)
    
    return text.strip()


def extract_keywords(text: str) -> List[str]:
    """Extract keywords from text for search"""
    if not text:
        return []
    
    # Simple keyword extraction - can be enhanced
    words = clean_text(text).lower().split()
    
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    return list(set(keywords))  # Remove duplicates


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def format_timestamp(timestamp: datetime) -> str:
    """Format timestamp for display"""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to specified length"""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length].rsplit(' ', 1)[0] + '...'
