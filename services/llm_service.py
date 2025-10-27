# backend/services/llm_service.py
import google.generativeai as genai
from core.config import settings
from typing import Dict, List, Any, Optional
import logging
import json
import re
from utils.prompts import INTENT_DETECTION_PROMPT
        

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

class LLMService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        """Generate response from LLM"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=2048,
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return "I apologize, but I'm having trouble processing your request. Please try again."
    
    # In backend/services/llm_service.py - Update the intent detection

    # In backend/services/llm_service.py - Update detect_intent method

    def detect_intent(self, user_input: str, conversation_history: List[Dict],
                    has_active_incident: bool, session_id: str) -> Dict[str, Any]:
        """Detect user intent using LLM with improved context awareness"""
        
        try:
            # Check for new issue descriptions when there's an active incident
            if has_active_incident:
                user_lower = user_input.lower().strip()
                
                # Clear indicators of new technical issues
                new_issue_indicators = [
                    'not opening', 'not working', 'not connecting', 'cannot access',
                    'failed', 'broken', 'error', 'issue with', 'problem with',
                    'outlook', 'email', 'vpn', 'network', 'wifi', 'software',
                    'install', 'password', 'login', 'access', 'connection'
                ]
                
                # If user describes a clear technical issue while having active incident
                if any(indicator in user_lower for indicator in new_issue_indicators):
                    # Check if it's different from current context
                    is_different_issue = True
                    if conversation_history:
                        last_bot_msg = conversation_history[-1].get('content', '').lower() if conversation_history[-1].get('role') == 'assistant' else ''
                        # If last bot message contains similar keywords, might be same issue
                        common_keywords = set(new_issue_indicators).intersection(set(last_bot_msg.split()))
                        if len(common_keywords) > 1:
                            is_different_issue = False
                    
                    if is_different_issue:
                        return {
                            "intent": "NEW_INCIDENT",
                            "confidence": 0.85,
                            "reasoning": "User described a new technical issue while having active incident"
                        }

            conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-10:]])
            
            is_after_greeting = False
            if len(conversation_history) >= 2:
                last_bot_msg = conversation_history[-1].get('content', '').lower() if conversation_history[-1].get('role') == 'assistant' else ''
                if 'track' in last_bot_msg and 'create' in last_bot_msg and 'how may i help' in last_bot_msg:
                    is_after_greeting = True

            prompt = INTENT_DETECTION_PROMPT.format(
                user_input=user_input,
                conversation_history=conv_text,
                has_active_incident=has_active_incident,
                session_id=session_id,
                is_after_greeting=is_after_greeting
            )
            
            response = self.generate_response(prompt, temperature=0.3)
            
            try:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    intent_data = json.loads(json_str)
                    logger.info(f"Detected intent: {intent_data}")
                    return intent_data
            except Exception as e:
                logger.error(f"Error parsing intent: {e}")
            
            # ✅ FIX: Ensure fallback always returns a dict
            return self._fallback_intent_detection(user_input, has_active_incident)
            
        except Exception as e:
            logger.error(f"Error in LLM intent detection: {e}")
            # ✅ FIX: Always return a fallback intent
            return self._fallback_intent_detection(user_input, has_active_incident)
        # ... rest of the method remains the same
    def _extract_context_keywords(self, conversation_history: List[Dict]) -> List[str]:
        """Extract keywords from recent conversation for context awareness"""
        recent_text = " ".join([msg['content'] for msg in conversation_history[-4:]])
        words = re.findall(r'\b\w+\b', recent_text.lower())
        # Return most frequent words (excluding common words)
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        word_freq = {}
        for word in words:
            if word not in common_words and len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1
        return sorted(word_freq, key=word_freq.get, reverse=True)[:5]
    
    def _is_related_to_context(self, user_input: str, context_keywords: List[str]) -> bool:
        """Check if user input is related to current context"""
        if not context_keywords:
            return False
        user_words = set(re.findall(r'\b\w+\b', user_input.lower()))
        overlap = user_words.intersection(set(context_keywords))
        return len(overlap) > 0
    
    def _is_technical_query(self, user_input: str) -> bool:
        """Check if query seems technical"""
        tech_keywords = {
            'install', 'error', 'problem', 'issue', 'not working', 'broken', 'fix',
            'password', 'login', 'access', 'vpn', 'network', 'wifi', 'email',
            'outlook', 'software', 'hardware', 'update', 'upgrade', 'reset'
        }
        user_words = set(re.findall(r'\b\w+\b', user_input.lower()))
        return len(user_words.intersection(tech_keywords)) > 0
    
    def _is_asking_about_previous_solution(self, user_input: str) -> bool:
        """Check if user is asking about previous incidents/solutions"""
        previous_keywords = {
            'previous', 'last', 'earlier', 'before', 'my incident', 'solution', 
            'what happened', 'status', 'view solution', 'continue my', 'old incident',
            'past incident', 'earlier issue'
        }
        user_lower = user_input.lower()
        return any(keyword in user_lower for keyword in previous_keywords)
    
    def _fallback_intent_detection(self, user_input: str, has_active_incident: bool) -> Dict[str, Any]:
        """Fallback intent detection using keyword matching"""
        user_lower = user_input.lower().strip()
        
        if any(word in user_lower for word in ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']):
            return {"intent": "GREETING", "confidence": 0.9}
        elif any(word in user_lower for word in ['track', 'check', 'status', 'view incident', 'my incident']):
            return {"intent": "TRACK_INCIDENT", "confidence": 0.8}
        elif any(word in user_lower for word in ['close', 'finish', 'done', 'complete incident', 'end incident']):
            return {"intent": "CLOSE_INCIDENT", "confidence": 0.8}
        elif any(word in user_lower for word in ['clear', 'exit', 'end session', 'start fresh', 'reset', 'new session', 'start', 'restart']):
            return {"intent": "CLEAR_SESSION", "confidence": 0.8}
        elif re.search(r'INC\d+', user_input):
            incident_id = re.search(r'INC\d+', user_input).group()
            return {"intent": "PROVIDE_INCIDENT_ID", "confidence": 0.9, "extracted_incident_id": incident_id}
        elif any(word in user_lower for word in ['previous', 'last', 'solution', 'view solution']):
            return {"intent": "ASK_PREVIOUS_SOLUTION", "confidence": 0.8}
        else:
            return {"intent": "CONTINUE_INCIDENT" if has_active_incident else "NEW_INCIDENT", "confidence": 0.6}
    
    def generate_greeting_response(self, user_input: str, conversation_history: List[Dict]) -> str:
        """Generate greeting response"""
        from utils.prompts import GREETING_RESPONSE_PROMPT
        
        conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]])
        
        prompt = GREETING_RESPONSE_PROMPT.format(
            user_input=user_input,
            conversation_history=conv_text
        )
        
        response = self.generate_response(prompt, temperature=0.7)
        return response
    
    def generate_multiple_incident_response(self, current_incident_id: str, 
                                           current_issue: str, user_input: str) -> str:
        """Generate response for handling multiple incidents"""
        from utils.prompts import MULTIPLE_INCIDENT_PROMPT
        
        prompt = MULTIPLE_INCIDENT_PROMPT.format(
            current_incident_id=current_incident_id,
            current_issue=current_issue,
            user_input=user_input
        )
        
        response = self.generate_response(prompt, temperature=0.7)
        return response
    
    def generate_incident_selection_message(self, incident_list: str, example_id: str) -> str:
        """Generate dynamic message for incident selection after KEEP choice"""
        from utils.prompts import INCIDENT_SELECTION_DYNAMIC_PROMPT
        
        prompt = INCIDENT_SELECTION_DYNAMIC_PROMPT.format(
            incident_list=incident_list,
            example_id=example_id
        )
        
        response = self.generate_response(prompt, temperature=0.7)
        return response
    def generate_incident_selection_retry_message(self, incident_list: str, example_id: str) -> str:
        """Generate retry message when incident ID not found"""
        from utils.prompts import INCIDENT_SELECTION_RETRY_PROMPT
        
        prompt = INCIDENT_SELECTION_RETRY_PROMPT.format(
            incident_list=incident_list,
            example_id=example_id
        )
        
        response = self.generate_response(prompt, temperature=0.7)
        return response
    def generate_track_incident_response(self, user_input: str, conversation_history: List[Dict]) -> str:
        """Generate response asking for incident ID"""
        from utils.prompts import TRACK_INCIDENT_PROMPT
        
        conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]])
        
        prompt = TRACK_INCIDENT_PROMPT.format(
            user_input=user_input,
            conversation_history=conv_text
        )
        
        response = self.generate_response(prompt, temperature=0.7)
        return response
    
    def generate_incident_status_response(self, incident_details: Dict) -> str:
        """Generate response about incident status"""
        from utils.prompts import INCIDENT_STATUS_RESPONSE_PROMPT
        
        prompt = INCIDENT_STATUS_RESPONSE_PROMPT.format(
            incident_details=json.dumps(incident_details, indent=2)
        )
        
        response = self.generate_response(prompt, temperature=0.7)
        return response
    
    def generate_close_incident_confirmation(self, incident_id: str, incident_issue: str) -> str:
        """Generate confirmation for closing incident"""
        from utils.prompts import CLOSE_INCIDENT_CONFIRMATION_PROMPT
        
        prompt = CLOSE_INCIDENT_CONFIRMATION_PROMPT.format(
            incident_id=incident_id,
            incident_issue=incident_issue
        )
        
        response = self.generate_response(prompt, temperature=0.7)
        return response
    
    def generate_clear_session_confirmation(self) -> str:
        """Generate confirmation for clearing session"""
        from utils.prompts import CLEAR_SESSION_CONFIRMATION_PROMPT
        
        response = self.generate_response(CLEAR_SESSION_CONFIRMATION_PROMPT, temperature=0.7)
        return response
    
    def generate_ask_incident_type_response(self, user_input: str, conversation_history: List[Dict]) -> str:
        """Generate response asking what type of issue user wants to report"""
        from utils.prompts import ASK_INCIDENT_TYPE_PROMPT
        
        conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]])
        
        prompt = ASK_INCIDENT_TYPE_PROMPT.format(
            user_input=user_input,
            conversation_history=conv_text
        )
    
        return self.generate_response(prompt, temperature=0.7)  
    def analyze_technical_issue(self, user_query: str, conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze if query is a technical issue and what info is needed"""
        from utils.prompts import NEW_INCIDENT_ANALYSIS_PROMPT
        
        conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]])
        
        prompt = NEW_INCIDENT_ANALYSIS_PROMPT.format(
            user_query=user_query,
            conversation_history=conv_text
        )
        
        response = self.generate_response(prompt, temperature=0.3)
        
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
            return {"is_technical_issue": False}
        except Exception as e:
            logger.error(f"Error parsing technical analysis: {e}")
            return {"is_technical_issue": False}
    
    def generate_kb_question(self, kb_entry: Dict[str, Any], user_input: str,
                           collected_info: Dict[str, Any], missing_info: List[str],
                           conversation_history: List[Dict[str, str]]) -> str:
        """Generate next question based on KB entry"""
        from utils.prompts import KB_QUESTION_PROMPT
        
        conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-10:]])
        
        prompt = KB_QUESTION_PROMPT.format(
            kb_entry=kb_entry.get('full_text', ''),
            conversation_history=conv_text,
            user_input=user_input,
            collected_info=json.dumps(collected_info, indent=2),
            missing_info=json.dumps(missing_info, indent=2)
        )
        
        response = self.generate_response(prompt, temperature=0.7)
        return response
    
    def handle_general_query(self, user_input: str, conversation_history: List[Dict]) -> str:
        """Handle general non-technical queries"""
        from utils.prompts import GENERAL_QUERY_PROMPT
        
        try:
            conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]])
            
            prompt = GENERAL_QUERY_PROMPT.format(
                user_input=user_input,
                conversation_history=conv_text
            )
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error handling general query: {e}")
            return "Hello! I'm the IT helpdesk assistant. How can I help you with technical issues today?"
    
    def handle_incident_context_switch(self, active_incidents: List[str],
                                      user_input: str,
                                      conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Handle when user has multiple active incidents"""
        from utils.prompts import INCIDENT_CONTEXT_SWITCH_PROMPT
        
        conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]])
        incidents_text = "\n".join([f"- {inc_id}" for inc_id in active_incidents])
        
        prompt = INCIDENT_CONTEXT_SWITCH_PROMPT.format(
            active_incidents=incidents_text,
            user_input=user_input,
            conversation_history=conv_text
        )
        
        response = self.generate_response(prompt, temperature=0.5)
        
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
            return {"is_new_incident": True, "clarification_message": "Which incident would you like to discuss?"}
        except Exception as e:
            logger.error(f"Error parsing incident context switch: {e}")
            return {"is_new_incident": True, "clarification_message": "Which incident would you like to discuss?"}
    
    def extract_info_from_response(self, user_input: str, question: str, required_field: str = "") -> Dict[str, Any]:
        """Extract structured information from user's response - FALLBACK ONLY"""
        # This is now only used as a fallback if direct pattern matching fails
        
        # Simple heuristic approach
        user_lower = user_input.lower().strip()
        
        # Check for very short answers (1-5 words) - usually valid
        word_count = len(user_input.split())
        if word_count <= 5 and len(user_input) > 1:
            return {
                "answers_question": True,
                "extracted_info": user_input.strip(),
                "is_relevant": True,
                "reasoning": "Short specific answer"
            }
        
        # Check for negative responses
        if any(word in user_lower for word in ['no error', 'none', 'nothing', "don't see", 'not seeing']):
            return {
                "answers_question": True,
                "extracted_info": user_input.strip(),
                "is_relevant": True,
                "reasoning": "Negative/none response"
            }
        
        # Default to accepting the response
        return {
            "answers_question": True,
            "extracted_info": user_input.strip(),
            "is_relevant": True,
            "reasoning": "Accepted as answer"
        }
    def generate_initial_greeting(self, user_input: str, conversation_history: List[Dict]) -> str:
        """Generate initial greeting message"""
        from utils.prompts import INITIAL_GREETING_PROMPT
        
        conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]])
        
        prompt = INITIAL_GREETING_PROMPT.format(
            user_input=user_input,
            conversation_history=conv_text
        )
        
        return self.generate_response(prompt, temperature=0.7)

    def generate_greeting_with_context(self, user_input: str, conversation_history: List[Dict], 
                                    current_incident: Dict, incident_id: str) -> str:
        """Generate greeting when user has active incident"""
        from utils.prompts import GREETING_WITH_CONTEXT_PROMPT
        
        conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]])
        
        incident_conversation = current_incident.get('conversation_history', []) if current_incident else []
        last_question = ""
        for msg in reversed(incident_conversation):
            if msg.get('role') == 'assistant':
                last_question = msg.get('content', '')
                break
        
        prompt = GREETING_WITH_CONTEXT_PROMPT.format(
            user_input=user_input,
            conversation_history=conv_text,
            incident_id=incident_id,
            last_question=last_question,
            has_pending_info=bool(current_incident and current_incident.get('status') == 'pending_info')
        )
        
        return self.generate_response(prompt, temperature=0.7)

    def generate_fresh_session_greeting(self) -> str:
        """Generate greeting for fresh session after clear"""
        from utils.prompts import FRESH_SESSION_GREETING_PROMPT
        
        return self.generate_response(FRESH_SESSION_GREETING_PROMPT, temperature=0.7)

    def generate_keep_ignore_message(self, new_issue: str, current_issue: str, incident_id: str) -> str:
        """Generate message asking user to keep or ignore previous incident"""
        from utils.prompts import KEEP_IGNORE_MESSAGE_PROMPT
        
        prompt = KEEP_IGNORE_MESSAGE_PROMPT.format(
            new_issue=new_issue,
            current_issue=current_issue,
            incident_id=incident_id
        )
        
        return self.generate_response(prompt, temperature=0.7)

    def generate_keep_ignore_clarification(self) -> str:
        """Generate clarification when user doesn't say KEEP or IGNORE clearly"""
        from utils.prompts import KEEP_IGNORE_CLARIFICATION_PROMPT
        
        return self.generate_response(KEEP_IGNORE_CLARIFICATION_PROMPT, temperature=0.7)

    def generate_incident_completion_message(self, incident_id: str) -> str:
        """Generate message when all information is collected"""
        from utils.prompts import INCIDENT_COMPLETION_PROMPT
        
        prompt = INCIDENT_COMPLETION_PROMPT.format(
            incident_id=incident_id
        )
        
        return self.generate_response(prompt, temperature=0.7)

    def generate_default_admin_message(self, status: str) -> str:
        """Generate default admin message for given status"""
        from utils.prompts import DEFAULT_ADMIN_MESSAGE_PROMPT
        
        prompt = DEFAULT_ADMIN_MESSAGE_PROMPT.format(
            status=status
        )
        
        return self.generate_response(prompt, temperature=0.5)
    
    def generate_polite_goodbye(self) -> str:
        """Generate polite goodbye without closing incidents"""
        from utils.prompts import POLITE_GOODBYE_PROMPT
        
        return self.generate_response(POLITE_GOODBYE_PROMPT, temperature=0.7)
    def generate_incident_creation_confirmation(self, issue_description: str) -> str:
        """Generate confirmation message before creating incident"""
        from utils.prompts import INCIDENT_CREATION_CONFIRMATION_PROMPT
        
        prompt = INCIDENT_CREATION_CONFIRMATION_PROMPT.format(
            issue_description=issue_description
        )
        
        return self.generate_response(prompt, temperature=0.7)
# Global LLM service instance
llm_service = LLMService()