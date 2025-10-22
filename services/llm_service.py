#backend/services/llm_service.py
import google.generativeai as genai
from core.config import settings
from typing import Dict, List, Any, Optional
import logging
import json
import re

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
    
    def detect_intent(self, user_input: str, conversation_history: List[Dict], 
                     has_active_incident: bool, session_id: str) -> Dict[str, Any]:
        """Detect user intent using LLM"""
        from utils.prompts import INTENT_DETECTION_PROMPT
        
        conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-10:]])
        
        # Check if this is right after a greeting
        is_after_greeting = False
        if len(conversation_history) >= 2:
            last_bot_msg = conversation_history[-1].get('content', '').lower() if conversation_history[-1].get('role') == 'assistant' else ''
            if 'track' in last_bot_msg and 'create' in last_bot_msg and 'how may i help' in last_bot_msg:
                is_after_greeting = True
        
        # Direct keyword check for common patterns right after greeting
        user_lower = user_input.lower().strip()
        
        if is_after_greeting:
            logger.info("Detected message right after greeting")
            # User just got the greeting, now responding
            if any(phrase in user_lower for phrase in ['track', 'check status', 'view incident', 'my incident', 'existing incident']):
                logger.info("User wants to track incident")
                return {"intent": "TRACK_INCIDENT", "confidence": 0.95, "reasoning": "User wants to track after greeting"}
            elif any(phrase in user_lower for phrase in ['create', 'new incident', 'report', 'open incident']):
                logger.info("User wants to create incident - asking for issue type")
                return {"intent": "ASK_INCIDENT_TYPE", "confidence": 0.95, "reasoning": "User said create incident but hasn't described problem yet"}
        
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
        
        # Fallback to simple keyword detection
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
    
    def generate_ask_incident_type_response(self) -> str:
        """Generate response asking what type of incident user wants to create"""
        return ("I'd be happy to help you create an incident. Could you please describe the technical issue you're experiencing?\n\n"
                "For example:\n"
                "- Email problems (Outlook not opening, can't send emails)\n"
                "- Network issues (VPN not connecting, WiFi problems)\n"
                "- Software installation requests\n"
                "- Password reset needed\n"
                "- System performance issues\n\n"
                "Please tell me what problem you're facing.")
    
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
        """Extract structured information from user's response"""
        prompt = f"""You are analyzing a user's response to determine if they answered the question properly.

Question that was asked: {question}
User's response: {user_input}
Information being collected: {required_field}

Analyze the response and determine:
1. Does the response directly answer the question? (yes/no)
2. What specific information did the user provide?
3. Is it a relevant and complete answer to what was asked?

Guidelines:
- If the user gives specific technical details (OS name, error codes, software names, etc.), that's relevant
- If the user says things like "no", "yes", "nothing", "I don't know", that can be valid depending on the question
- If the user goes off-topic or provides unrelated information, that's not relevant

Respond in JSON format:
{{
    "answers_question": true/false,
    "extracted_info": "the specific information provided",
    "is_relevant": true/false,
    "reasoning": "brief explanation"
}}"""
        
        response = self.generate_response(prompt, temperature=0.3)
        
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                logger.info(f"Extracted info: {parsed}")
                return parsed
            return {"answers_question": True, "extracted_info": user_input, "is_relevant": True}
        except Exception as e:
            logger.error(f"Error extracting info: {e}")
            return {"answers_question": True, "extracted_info": user_input, "is_relevant": True}

# Global LLM service instance
llm_service = LLMService()