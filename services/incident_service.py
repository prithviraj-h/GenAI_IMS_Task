# backend/services/incident_service.py - COMPLETE CORRECTED VERSION
from db.mongo import mongo_client
from services.kb_service import kb_service
from services.llm_service import llm_service
from utils.preprocessing import generate_incident_id
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import uuid
import re

logger = logging.getLogger(__name__)

class IncidentService:
    
    def __init__(self):
        pass
    
    def create_session(self) -> str:
        """Create a new session"""
        session_id = str(uuid.uuid4())
        session_data = {
            'session_id': session_id,
            'active_incidents': [],
            'conversation_context': [],
            'awaiting_response': None,
            'created_on': datetime.utcnow(),
            'updated_on': datetime.utcnow()
        }
        mongo_client.create_session(session_data)
        return session_id
    
    def get_or_create_session(self, session_id: Optional[str]) -> str:
        """Get existing session or create new one"""
        if session_id:
            session = mongo_client.get_session(session_id)
            if session:
                return session_id
        
        return self.create_session()
    
    def clear_session(self, session_id: str) -> bool:
        """Clear session history and start fresh"""
        try:
            mongo_client.update_session(session_id, {
                'conversation_context': [],
                'active_incidents': [],
                'awaiting_response': None,
                'updated_on': datetime.utcnow()
            })
            logger.info(f"Session cleared: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return False
   
    def update_session_context(self, session_id: str, user_input: str, assistant_response: str):
        """Update session conversation context - keep only last 10 messages"""
        session = mongo_client.get_session(session_id)
        if session:
            conversation_context = session.get('conversation_context', [])
            conversation_context.append({'role': 'user', 'content': user_input})
            conversation_context.append({'role': 'assistant', 'content': assistant_response})
            
            if len(conversation_context) > 10:
                conversation_context = conversation_context[-10:]
            
            mongo_client.update_session(session_id, {
                'conversation_context': conversation_context
            })

    def add_incident_to_session(self, session_id: str, incident_id: str):
        """Add incident to session's active incidents"""
        session = mongo_client.get_session(session_id)
        if session:
            active_incidents = session.get('active_incidents', [])
            if incident_id not in active_incidents:
                active_incidents.append(incident_id)
                mongo_client.update_session(session_id, {
                    'active_incidents': active_incidents
                })
    
    def remove_incident_from_session(self, session_id: str, incident_id: str):
        """Remove incident from session's active incidents"""
        session = mongo_client.get_session(session_id)
        if session:
            active_incidents = session.get('active_incidents', [])
            if incident_id in active_incidents:
                active_incidents.remove(incident_id)
                mongo_client.update_session(session_id, {
                    'active_incidents': active_incidents
                })
    
    def get_session_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get session conversation history"""
        session = mongo_client.get_session(session_id)
        if session:
            return session.get('conversation_context', [])
        return []
    
    # In the process_user_query method, replace the section that checks for new issue descriptions:

    # In the process_user_query method, make sure ALL code paths return a dictionary

    def process_user_query(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """Main method to process user query with intent detection"""
        try:
            session_id = self.get_or_create_session(session_id)
            session = mongo_client.get_session(session_id)
            
            if not session:
                logger.error(f"Failed to get or create session: {session_id}")
                return self._create_error_response(session_id, "Failed to create session")
            
            conversation_history = session.get('conversation_context', [])
            if len(conversation_history) > 10:
                conversation_history = conversation_history[-10:]
                mongo_client.update_session(session_id, {
                    'conversation_context': conversation_history
                })
            
            active_incidents = session.get('active_incidents', [])
            awaiting_response = session.get('awaiting_response')
            
            has_active_incident = len(active_incidents) > 0
            
            # ✅ NEW: Handle issue_description response
            if awaiting_response == 'issue_description':
                logger.info(f"User provided issue description: '{user_input}'")
                
                # Clear awaiting response
                mongo_client.update_session(session_id, {
                    'awaiting_response': None
                })
                
                # ✅ Generate confirmation message before creating incident
                confirmation = llm_service.generate_incident_creation_confirmation(user_input)
                self.update_session_context(session_id, user_input, confirmation)
                
                # Add confirmation message
                temp_response = {
                    'message': confirmation,
                    'session_id': session_id,
                    'incident_id': None,
                    'status': 'confirming_creation'
                }
                
                # Now create the incident
                if has_active_incident:
                    return self._handle_new_incident_with_active(user_input, session_id, conversation_history, active_incidents)
                else:
                    return self._handle_new_incident(user_input, session_id, conversation_history)
            
            # Handle keep/ignore response FIRST
            if awaiting_response == 'keep_or_ignore':
                return self._handle_keep_ignore_response(user_input, session_id, conversation_history, active_incidents)
            
            # Handle other awaiting responses
            if awaiting_response == 'issue_description':
                mongo_client.update_session(session_id, {
                    'awaiting_response': None
                })
                return self._handle_new_incident(user_input, session_id, conversation_history)
            
            if awaiting_response == 'previous_solution_id':
                return self._handle_previous_solution_id(user_input, session_id, conversation_history, [])
            
            if awaiting_response == 'incident_id_selection':
                return self._handle_incident_selection(user_input, session_id, conversation_history, active_incidents)
            
            # Improved detection for new issue descriptions
            if has_active_incident and not awaiting_response:
                current_incident_id = active_incidents[-1]
                current_incident = mongo_client.get_incident_by_id(current_incident_id)
                
                if current_incident and current_incident.get('status') == 'pending_info':
                    # Check if this is clearly a NEW issue description (not an answer)
                    is_new_issue = self._is_clearly_new_issue_description(user_input, current_incident)
                    
                    if is_new_issue:
                        logger.info(f"🎯 User describing NEW issue while active incident exists → KEEP/IGNORE: '{user_input}'")
                        return self._handle_new_incident_with_active(user_input, session_id, conversation_history, active_incidents)
            
            # Check for short answers with active incident (only if it's not a new issue)
            if has_active_incident and not awaiting_response:
                user_lower = user_input.lower().strip()
                word_count = len(user_input.split())
                
                # Only treat as CONTINUE_INCIDENT if it's likely an answer, not a new issue
                is_likely_answer = self._is_likely_answer_to_current_question(user_input, active_incidents)
                
                if word_count <= 7 and is_likely_answer:
                    not_command = not any(cmd in user_lower for cmd in [
                        'create incident', 'track incident', 'new incident', 
                        'close incident', 'clear session', 'view incomplete',
                        'view previous', 'hello', 'hi', 'hey', 'good morning'
                    ])
                    
                    if not_command:
                        logger.info(f"🎯 Short answer with active incident → CONTINUE_INCIDENT: '{user_input}'")
                        pending_incidents = self._get_pending_incidents(active_incidents)
                        if pending_incidents:
                            return self._continue_incident(pending_incidents[-1], user_input, session_id, conversation_history)
            
            # Detect user intent using LLM
            intent_data = llm_service.detect_intent(
                user_input,
                conversation_history,
                has_active_incident,
                session_id
            )
            
            # ✅ FIX: Ensure intent_data is not None
            if not intent_data:
                logger.error("LLM intent detection returned None, using fallback")
                intent_data = self._fallback_intent_detection(user_input, has_active_incident)
            
            intent = intent_data.get('intent', 'GENERAL_QUERY')
            logger.info(f"Processing intent: {intent}")
            
            # Handle different intents - ensure ALL return a value
            if intent == 'GREETING':
                return self._handle_greeting(user_input, session_id, conversation_history)
            
            elif intent == 'GREETING_CONTEXT':
                return self._handle_greeting_context(user_input, session_id, conversation_history, active_incidents)
            
            elif intent == 'UNRELATED_QUERY':
                return self._handle_unrelated_query(user_input, session_id, conversation_history, active_incidents)
            
            elif intent == 'CLEAR_SESSION':
                return self._handle_clear_session(session_id, conversation_history, user_input)
            
            elif intent == 'TRACK_INCIDENT':
                return self._handle_track_incident_request(user_input, session_id, conversation_history)
            
            elif intent == 'ASK_INCIDENT_TYPE':
                return self._handle_ask_incident_type(user_input, session_id, conversation_history)
            
            elif intent == 'ASK_INCOMPLETE_INCIDENT':
                return self._handle_ask_incomplete_incident(user_input, session_id, conversation_history)
            
            elif intent == 'PROVIDE_INCIDENT_ID':
                incident_id = intent_data.get('extracted_incident_id')
                return self._handle_track_incident_by_id(incident_id, user_input, session_id, conversation_history)
            
            elif intent == 'CLOSE_INCIDENT':
                return self._handle_close_incident(active_incidents, user_input, session_id, conversation_history)
            
            elif intent == 'ASK_PREVIOUS_SOLUTION':
                return self._handle_ask_previous_solution(user_input, session_id, conversation_history)
            
            elif intent == 'NEW_INCIDENT':
                if has_active_incident:
                    return self._handle_new_incident_with_active(user_input, session_id, conversation_history, active_incidents)
                else:
                    return self._handle_new_incident(user_input, session_id, conversation_history)
            
            elif intent == 'CONTINUE_INCIDENT':
                pending_incidents = self._get_pending_incidents(active_incidents)
                if pending_incidents:
                    return self._continue_incident(pending_incidents[-1], user_input, session_id, conversation_history)
                else:
                    return self._handle_new_incident(user_input, session_id, conversation_history)
            
            else:
                # ✅ FIX: Ensure this always returns a value
                response = llm_service.handle_general_query(user_input, conversation_history)
                self.update_session_context(session_id, user_input, response)
                return {
                    'message': response,
                    'session_id': session_id,
                    'incident_id': None,
                    'status': None
                }
            
        except Exception as e:
            logger.error(f"Error processing user query: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # ✅ FIX: Always return a proper error response
            return self._create_error_response(session_id, str(e))

    # ✅ ADD NEW METHOD: Create standardized error response
    def _create_error_response(self, session_id: str, error_msg: str = "") -> Dict[str, Any]:
        """Create a standardized error response"""
        return {
            'message': "I apologize, but I encountered an error processing your request. Please try again.",
            'session_id': session_id or "",
            'incident_id': None,
            'status': 'error'
        }

    # ✅ ADD NEW METHOD: Fallback intent detection
    def _fallback_intent_detection(self, user_input: str, has_active_incident: bool) -> Dict[str, Any]:
        """Fallback intent detection when LLM fails"""
        user_lower = user_input.lower().strip()
        
        if any(word in user_lower for word in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']):
            return {"intent": "GREETING", "confidence": 0.9}
        elif any(word in user_lower for word in ['track', 'check', 'status', 'view incident']):
            return {"intent": "TRACK_INCIDENT", "confidence": 0.8}
        elif any(word in user_lower for word in ['create', 'new incident', 'report']):
            return {"intent": "NEW_INCIDENT", "confidence": 0.8}
        elif re.search(r'INC\d+', user_input):
            incident_id = re.search(r'INC\d+', user_input).group()
            return {"intent": "PROVIDE_INCIDENT_ID", "confidence": 0.9, "extracted_incident_id": incident_id}
        else:
            return {"intent": "CONTINUE_INCIDENT" if has_active_incident else "NEW_INCIDENT", "confidence": 0.6}

    # ✅ ADD NEW METHOD: Improved detection for new issues
    def _is_clearly_new_issue_description(self, user_input: str, current_incident: Dict) -> bool:
        """Check if user input is clearly describing a new technical issue"""
        user_lower = user_input.lower().strip()
        current_issue = current_incident.get('user_demand', '').lower()
        
        # ✅ FIX: Check for "no error" or similar negative responses FIRST
        negative_error_responses = [
            'no error', 'no errors', 'none', 'nothing', 'not seeing', 
            "don't see", 'no error message', 'no message'
        ]
        if any(phrase in user_lower for phrase in negative_error_responses):
            logger.info(f"✅ Detected negative error response, NOT a new issue: '{user_input}'")
            return False  # This is an answer, not a new issue
        
        # Common technical issue patterns that indicate NEW issues
        new_issue_patterns = [
            'not opening', 'not working', 'not connecting', 'cannot access', 'failed',
            'broken', 'error', 'issue with', 'problem with', 'trouble with',
            'outlook', 'email', 'vpn', 'network', 'wifi', 'software', 'hardware',
            'install', 'password', 'login', 'access', 'connection', 'performance',
            'slow', 'crash', 'freeze', 'hang', 'unresponsive'
        ]
        
        # Check if input matches new issue patterns
        has_issue_keywords = any(pattern in user_lower for pattern in new_issue_patterns)
        
        # Get current question context
        current_missing_info = current_incident.get('missing_info', [])
        current_field = current_missing_info[0] if current_missing_info else ""
        
        # Check if this is NOT answering the current question
        is_not_answer = True
        if current_field:
            field_lower = current_field.lower()
            # If the user input seems to answer the current field, it's not a new issue
            if any(keyword in field_lower for keyword in ['operating system', 'os']):
                is_not_answer = not any(os in user_lower for os in ['windows', 'mac', 'linux', 'macos'])
            elif 'vpn client' in field_lower:
                is_not_answer = not any(vpn in user_lower for vpn in ['cisco', 'anyconnect', 'globalprotect'])
            elif 'error message' in field_lower or 'error code' in field_lower:
                # ✅ FIX: Check for error-related responses
                is_not_answer = not any(word in user_lower for word in ['error', 'code', 'message', 'no', 'none'])
            elif 'account type' in field_lower:
                is_not_answer = not any(acc in user_lower for acc in ['office365', 'exchange', 'gmail'])
        
        # Check if it describes a different issue than current one
        is_different_issue = True
        if current_issue:
            current_issue_keywords = set(current_issue.split())
            user_keywords = set(user_lower.split())
            # If they share significant keywords, might be same issue
            common_keywords = current_issue_keywords.intersection(user_keywords)
            if len(common_keywords) > 2:  # If they share more than 2 keywords, likely same issue
                is_different_issue = False
        
        logger.info(f"New issue check - Keywords: {has_issue_keywords}, Not answer: {is_not_answer}, Different: {is_different_issue}")
        
        return has_issue_keywords and is_not_answer and is_different_issue
    # ✅ ADD NEW METHOD: Check if input is likely an answer to current question
    def _is_likely_answer_to_current_question(self, user_input: str, active_incidents: List[str]) -> bool:
        """Check if user input is likely answering the current question"""
        if not active_incidents:
            return False
        
        current_incident_id = active_incidents[-1]
        current_incident = mongo_client.get_incident_by_id(current_incident_id)
        
        if not current_incident or current_incident.get('status') != 'pending_info':
            return False
        
        current_missing_info = current_incident.get('missing_info', [])
        if not current_missing_info:
            return False
        
        current_field = current_missing_info[0].lower()
        user_lower = user_input.lower().strip()
        
        # Check if this looks like an answer to the current field
        if 'operating system' in current_field or 'os' in current_field:
            return any(os in user_lower for os in ['windows', 'mac', 'linux', 'macos', 'ubuntu'])
        elif 'vpn client' in current_field:
            return any(vpn in user_lower for vpn in ['cisco', 'anyconnect', 'globalprotect', 'forticlient'])
        elif 'error message' in current_field or 'error code' in current_field:
            # ✅ FIX: Accept both positive and negative error responses
            return (
                'error' in user_lower or 
                any(phrase in user_lower for phrase in ['no error', 'none', 'nothing', 'not seeing', "don't see"])
            )
        elif 'account type' in current_field:
            return any(acc in user_lower for acc in ['office365', 'exchange', 'gmail', 'outlook'])
        elif 'network type' in current_field:
            return any(net in user_lower for net in ['home', 'office', 'wifi', 'ethernet'])
        else:
            # For generic fields, check if it's a short specific answer
            word_count = len(user_input.split())
            return word_count <= 5 and len(user_input) > 1    
    def _is_new_issue_description(self, user_input: str, current_incident: Dict) -> bool:
        """Check if user input is clearly describing a new issue vs answering current question"""
        user_lower = user_input.lower().strip()
        current_issue = current_incident.get('user_demand', '').lower()
        
        # Keywords that indicate a new issue description
        new_issue_keywords = [
            'not opening', 'not working', 'not connecting', 'cannot access',
            'broken', 'failed', 'error', 'issue with', 'problem with',
            'outlook', 'email', 'vpn', 'network', 'wifi', 'software',
            'install', 'password', 'login'
        ]
        
        # Check if this looks like a complete issue description
        has_new_issue_keywords = any(keyword in user_lower for keyword in new_issue_keywords)
        is_complete_sentence = len(user_input.split()) > 3
        
        # Check if it's NOT answering the current question
        current_missing_info = current_incident.get('missing_info', [])
        current_field = current_missing_info[0] if current_missing_info else ""
        
        # If user is describing a different issue than current one
        is_different_issue = (current_issue not in user_lower and 
                             not any(field.lower() in user_lower for field in current_missing_info))
        
        return has_new_issue_keywords and is_complete_sentence and is_different_issue

    def _handle_greeting(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle greeting intent - NEVER closes incidents"""
        user_lower = user_input.lower().strip()
        
        # Check if it's a goodbye/thank you
        is_goodbye = any(word in user_lower for word in ['bye', 'goodbye', 'thanks', 'thank you'])
        
        if is_goodbye:
            # ✅ Use LLM to generate polite goodbye without closing incidents
            response = llm_service.generate_polite_goodbye()
        else:
            # ✅ Use LLM to generate initial greeting
            response = llm_service.generate_initial_greeting(user_input, conversation_history)
        
        self.update_session_context(session_id, user_input, response)
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': None,
            'show_action_buttons': True,
            'action_buttons': [
                {'label': 'Track Incident', 'value': 'track a incident'},
                {'label': 'Create New Incident', 'value': 'create a incident'},
                {'label': 'View Incomplete Incident', 'value': 'view incomplete incident'}
            ]
        }
    
    def _handle_greeting_context(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle greeting while there's an active incident"""
        current_incident_id = active_incidents[-1] if active_incidents else None
        current_incident = mongo_client.get_incident_by_id(current_incident_id) if current_incident_id else None
        
        # ✅ Use LLM to generate contextual greeting
        response = llm_service.generate_greeting_with_context(
            user_input,
            conversation_history,
            current_incident,
            current_incident_id
        )
        
        self.update_session_context(session_id, user_input, response)
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': current_incident_id,
            'status': current_incident.get('status') if current_incident else None
        }
    
    def _handle_unrelated_query(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle unrelated query during active incident"""
        if active_incidents:
            current_incident_id = active_incidents[-1]
            current_incident = mongo_client.get_incident_by_id(current_incident_id)
            
            if current_incident and current_incident.get('status') == 'pending_info':
                incident_conversation = current_incident.get('conversation_history', [])
                last_question = ""
                for msg in reversed(incident_conversation):
                    if msg.get('role') == 'assistant':
                        last_question = msg.get('content', '')
                        break
                
                response = f"I understand you're asking about something else. Let's first complete your current incident.\n\n{last_question}"
            else:
                response = "I notice we were discussing a different topic. Would you like to continue with that or start something new?"
        else:
            response = llm_service.handle_general_query(user_input, conversation_history)
        
        self.update_session_context(session_id, user_input, response)
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': current_incident_id if active_incidents else None,
            'status': current_incident.get('status') if current_incident else None
        }
    
    def _handle_clear_session(self, session_id: str, conversation_history: List[Dict], user_input: str) -> Dict[str, Any]:
        """Handle clear session intent"""
        self.clear_session(session_id)
        
        response = llm_service.generate_fresh_session_greeting()
        self.update_session_context(session_id, user_input, response)
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': 'session_cleared',
            'action': 'clear_session',
            'show_action_buttons': True,
            'action_buttons': [
                {'label': 'Track Incident', 'value': 'track a incident'},
                {'label': 'Create New Incident', 'value': 'create a incident'},
                {'label': 'View Incomplete Incident', 'value': 'view incomplete incident'}
            ]
        }
    
    def _handle_track_incident_request(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle request to track an incident"""
        response = llm_service.generate_track_incident_response(user_input, conversation_history)
        self.update_session_context(session_id, user_input, response)
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': 'awaiting_incident_id'
        }
    
    def _handle_track_incident_by_id(self, incident_id: str, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle tracking incident by ID with admin message"""
        try:
            incident = mongo_client.get_incident_by_id(incident_id)
            
            if not incident:
                response = f"I couldn't find an incident with ID: {incident_id}. Please check the ID and try again."
                self.update_session_context(session_id, user_input, response)
                return {
                    'message': response,
                    'session_id': session_id,
                    'incident_id': None,
                    'status': 'not_found'
                }
            
            admin_message = incident.get('admin_message', '')
            if not admin_message:
                admin_message = self._get_default_admin_message(incident.get('status', ''))
            
            incident_details = {
                'incident_id': incident.get('incident_id'),
                'status': incident.get('status'),
                'user_demand': incident.get('user_demand'),
                'collected_info': incident.get('collected_info', {}),
                'admin_message': admin_message,
                'created_on': str(incident.get('created_on')),
                'updated_on': str(incident.get('updated_on'))
            }
            
            response = llm_service.generate_incident_status_response(incident_details)
            self.update_session_context(session_id, user_input, response)
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': incident_id,
                'status': incident.get('status')
            }
            
        except Exception as e:
            logger.error(f"Error tracking incident: {e}")
            response = "I encountered an error while retrieving the incident. Please try again."
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'error'
            }
    
    def _handle_close_incident(self, active_incidents: List[str], user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle close incident intent"""
        if not active_incidents:
            response = "You don't have any active incidents to close."
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': None
            }
        
        incident_id = active_incidents[-1]
        incident = mongo_client.get_incident_by_id(incident_id)
        
        if incident:
            mongo_client.update_incident(incident_id, {
                'status': 'closed',
                'closed_on': datetime.utcnow()
            })
            
            self.remove_incident_from_session(session_id, incident_id)
            
            response = llm_service.generate_close_incident_confirmation(
                incident_id, 
                incident.get('user_demand', 'your issue')
            )
            
            self.update_session_context(session_id, user_input, response)
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': incident_id,
                'status': 'closed'
            }
        else:
            response = "I couldn't find the incident to close. Please try again."
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'error'
            }
    
    def _handle_ask_previous_solution(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle request to view previous solution or continue incident"""
        response = "I'd be happy to help you with a previous incident. Please provide the Incident ID (e.g., INC20251022150744) for which you'd like to view the solution or continue the conversation."
        self.update_session_context(session_id, user_input, response)
        
        mongo_client.update_session(session_id, {
            'awaiting_response': 'previous_solution_id'
        })
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': 'awaiting_previous_incident_id'
        }
    
    def _handle_ask_incomplete_incident(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle request to view incomplete incident"""
        response = "I'd be happy to help you continue an incomplete incident. Please provide the Incident ID (e.g., INC20251022150744) to continue from where you left off:"
        self.update_session_context(session_id, user_input, response)
        
        mongo_client.update_session(session_id, {
            'awaiting_response': 'previous_solution_id'
        })
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': 'awaiting_previous_incident_id'
        }
    
    def _handle_previous_solution_id(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle incident ID provided for previous solution/incomplete incident request"""
        incident_id_match = re.search(r'INC\d+', user_input)
        
        if not incident_id_match:
            response = "I couldn't find a valid Incident ID in your message. Please provide the Incident ID (e.g., INC20251022150744):"
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_previous_incident_id'
            }
        
        incident_id = incident_id_match.group()
        incident = mongo_client.get_incident_by_id(incident_id)
        
        if not incident:
            response = f"No previous incident found for ID: {incident_id}. Please check the ID and try again."
            self.update_session_context(session_id, user_input, response)
            
            mongo_client.update_session(session_id, {
                'awaiting_response': None
            })
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'incident_not_found'
            }
        
        mongo_client.update_session(session_id, {
            'awaiting_response': None
        })
        
        if incident.get('status') in ['pending_info', 'open']:
            response_prefix = f"📋 Continuing with **{incident_id}** from where you left off.\n\n"
            response_prefix += f"**Issue:** {incident.get('user_demand', 'Unknown issue')}\n\n"
            
            incident_conversation = incident.get('conversation_history', [])
            missing_info = incident.get('missing_info', [])
            
            if incident_conversation:
                last_question = ""
                for msg in reversed(incident_conversation):
                    if msg.get('role') == 'assistant':
                        last_question = msg.get('content', '')
                        break
                
                if last_question:
                    response = response_prefix + "Let's continue: " + last_question
                else:
                    if missing_info:
                        response = response_prefix + f"Can you provide information about: {missing_info[0]}?"
                    else:
                        response = response_prefix + "Can you provide more details about this issue?"
            else:
                if missing_info:
                    response = response_prefix + f"Can you provide information about: {missing_info[0]}?"
                else:
                    response = response_prefix + "Can you provide more details about this issue?"
            
            self.update_session_context(session_id, user_input, response)
            self.add_incident_to_session(session_id, incident_id)
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': incident_id,
                'status': 'pending_info'
            }
        
        elif incident.get('status') == 'resolved':
            solution_steps = incident.get('solution_steps', 'No solution steps provided yet.')
            admin_message = incident.get('admin_message', '')
            
            response = f"**Incident {incident_id} - Solution Details**\n\n"
            response += f"**Issue:** {incident.get('user_demand', 'Unknown issue')}\n\n"
            response += f"**Solution:**\n{solution_steps}\n\n"
            
            if admin_message:
                response += f"**Message from Admin:** {admin_message}\n\n"
            
            response += "This incident has been resolved. Is there anything else I can help you with?"
            
            self.update_session_context(session_id, user_input, response)
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': incident_id,
                'status': 'solution_displayed'
            }
        
        else:
            response = f"Incident {incident_id} is currently in **{incident.get('status')}** status. "
            
            if incident.get('status') == 'resolved':
                response += "This incident has been resolved. "
            
            response += "Would you like to create a new incident?"
            
            self.update_session_context(session_id, user_input, response)
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': incident_id,
                'status': incident.get('status')
            }
    
    def _handle_new_incident_with_active(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle new incident when user has active incidents"""
        current_incident_id = active_incidents[-1]
        current_incident = mongo_client.get_incident_by_id(current_incident_id)
        current_issue = current_incident.get('user_demand', 'your current issue') if current_incident else 'your current issue'
        
        # ✅ Use LLM to generate keep/ignore message
        response = llm_service.generate_keep_ignore_message(
            user_input,
            current_issue,
            current_incident_id
        )
        
        self.update_session_context(session_id, user_input, response)
        
        mongo_client.update_session(session_id, {
            'awaiting_response': 'keep_or_ignore',
            'pending_new_incident_query': user_input
        })
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': current_incident_id,
            'status': 'awaiting_decision',
            'show_action_buttons': True,
            'action_buttons': [
                {'label': 'KEEP', 'value': 'keep'},
                {'label': 'IGNORE', 'value': 'ignore'}
            ]
        }
    
    # In backend/services/incident_service.py
# Replace the _handle_keep_ignore_response method with this fixed version:

    def _handle_keep_ignore_response(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle user's response to keep or ignore previous incident"""
        user_lower = user_input.lower().strip()
        session = mongo_client.get_session(session_id)
        pending_query = session.get('pending_new_incident_query', '')
        
        if 'ignore' in user_lower:
            logger.info(f"User chose IGNORE - closing incidents: {active_incidents}")
            
            # Delete all active incidents from database
            for incident_id in active_incidents:
                try:
                    result = mongo_client.incidents_collection.delete_one({'incident_id': incident_id})
                    if result.deleted_count > 0:
                        logger.info(f"✅ Deleted incident: {incident_id}")
                    else:
                        logger.warning(f"⚠️ Could not delete incident: {incident_id}")
                except Exception as e:
                    logger.error(f"❌ Error deleting incident {incident_id}: {e}")
            
            # Clear the session completely
            mongo_client.update_session(session_id, {
                'conversation_context': [],
                'active_incidents': [],
                'pending_new_incident_query': None,
                'awaiting_response': None
            })
            
            logger.info(f"✅ Session cleared and incidents deleted for IGNORE choice")
            
            # Process new incident with completely fresh session
            return self._handle_new_incident(pending_query if pending_query else user_input, session_id, [])
        
        elif 'keep' in user_lower:
            logger.info(f"User chose KEEP - creating new incident alongside: {active_incidents}")
            
            # Create the new incident first
            kb_result = kb_service.search_kb(pending_query)
            new_incident_id = None
            
            if kb_result['best_match']:
                new_incident_id = generate_incident_id()
                best_match = kb_result['best_match']
                
                incident_data = {
                    'incident_id': new_incident_id,
                    'user_demand': pending_query,
                    'session_id': session_id,
                    'status': 'pending_info',
                    'kb_id': best_match['kb_id'],
                    'collected_info': {},
                    'required_info': best_match['required_info'],
                    'missing_info': best_match['required_info'].copy(),
                    'questions': best_match['questions'],
                    'solution_steps': best_match['solution_steps'],
                    'conversation_history': [],
                    'is_new_kb_entry': False,
                    'needs_kb_approval': False,
                    'requires_kb_addition': False,
                    'admin_message': '',
                    'created_on': datetime.utcnow(),
                    'updated_on': datetime.utcnow()
                }
                
                mongo_client.create_incident(incident_data)
                self.add_incident_to_session(session_id, new_incident_id)
                
            else:
                analysis = llm_service.analyze_technical_issue(pending_query, conversation_history)
                
                if analysis.get('is_technical_issue'):
                    new_incident_id = generate_incident_id()
                    required_info = analysis.get('required_info', [])
                    questions = analysis.get('clarifying_questions', [])
                    
                    incident_data = {
                        'incident_id': new_incident_id,
                        'user_demand': pending_query,
                        'session_id': session_id,
                        'status': 'pending_info',
                        'kb_id': None,
                        'collected_info': {},
                        'required_info': required_info,
                        'missing_info': required_info.copy(),
                        'questions': questions,
                        'solution_steps': '',
                        'conversation_history': [],
                        'is_new_kb_entry': True,
                        'needs_kb_approval': True,
                        'requires_kb_addition': True,
                        'admin_message': '',
                        'created_on': datetime.utcnow(),
                        'updated_on': datetime.utcnow()
                    }
                    
                    mongo_client.create_incident(incident_data)
                    self.add_incident_to_session(session_id, new_incident_id)
            
            # Get updated session with both incidents
            updated_session = mongo_client.get_session(session_id)
            all_incidents = updated_session.get('active_incidents', [])
            
            # ✅ NEW: Use LLM to generate the incident selection message dynamically
            incident_list_text = self._format_incident_list(all_incidents)
            
            response = llm_service.generate_incident_selection_message(
                incident_list_text,
                all_incidents[0] if all_incidents else 'INC20251022150744'
            )
            
            self.update_session_context(session_id, user_input, response)
            
            # Clear the pending query and set awaiting response
            mongo_client.update_session(session_id, {
                'awaiting_response': 'incident_id_selection',
                'pending_new_incident_query': None
            })
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_incident_selection',
                'show_action_buttons': False
            }
        
        else:
            # User didn't say KEEP or IGNORE clearly
            response = llm_service.generate_keep_ignore_clarification()
            self.update_session_context(session_id, user_input, response)
            
            mongo_client.update_session(session_id, {
                'awaiting_response': 'keep_or_ignore',
                'pending_new_incident_query': pending_query
            })
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_decision',
                'show_action_buttons': True,
                'action_buttons': [
                    {'label': 'KEEP', 'value': 'keep'},
                    {'label': 'IGNORE', 'value': 'ignore'}
                ]
            }

    def _is_answer_to_error_question(self, user_input: str, current_incident: Dict) -> bool:
        """Check if user is answering an error message question"""
        user_lower = user_input.lower().strip()
        
        # Get the last question asked
        conversation = current_incident.get('conversation_history', [])
        last_question = ""
        for msg in reversed(conversation):
            if msg.get('role') == 'assistant':
                last_question = msg.get('content', '').lower()
                break
        
        # Check if last question was about errors
        is_error_question = any(word in last_question for word in ['error', 'error code', 'error message'])
        
        # Check if user is saying "no error" or similar
        is_no_error_response = any(phrase in user_lower for phrase in [
            'no error', 'no errors', 'none', 'nothing', 'not seeing', "don't see", 
            'no message', 'no code', 'nope', "doesn't show"
        ])
        
        return is_error_question and is_no_error_response

    
    def _format_incident_list(self, incident_ids: List[str]) -> str:
        """Format incident list - one per line with bullet"""
        incident_lines = []
        
        for inc_id in incident_ids:
            inc = mongo_client.get_incident_by_id(inc_id)
            if inc:
                issue_desc = inc.get('user_demand', 'Unknown issue')
                # ✅ Format: • INC20251026125046 - outlook is not working
                incident_lines.append(f"• {inc_id} - {issue_desc}")
        
        return "\n".join(incident_lines)
    
    def _handle_incident_selection(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle incident ID selection after user chose KEEP"""
        incident_id_match = re.search(r'INC\d+', user_input)
        
        if not incident_id_match:
            # ✅ Use dynamic formatting
            incident_list_text = self._format_incident_list(active_incidents)
            
            response = llm_service.generate_incident_selection_retry_message(
                incident_list_text,
                active_incidents[0] if active_incidents else 'INC20251022150744'
            )
            
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_incident_selection'
            }
        
        selected_incident_id = incident_id_match.group()
        incident = mongo_client.get_incident_by_id(selected_incident_id)
        
        if not incident:
            response = f"❌ Incident **{selected_incident_id}** not found. Please provide a valid Incident ID from the list above:"
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_incident_selection'
            }
        
        mongo_client.update_session(session_id, {
            'awaiting_response': None
        })
        
        if incident.get('status') == 'pending_info':
            logger.info(f"Continuing with incident {selected_incident_id}")
            dummy_input = "continue"
            return self._continue_incident(incident, dummy_input, session_id, conversation_history)
        
        else:
            response = f"📋 **{selected_incident_id}** - Status: **{incident.get('status')}**\n\n"
            
            if incident.get('status') == 'open':
                response += "✅ All required information has been collected. Our IT team is working on this. Is there anything else you'd like to add?"
            elif incident.get('status') == 'resolved':
                response += "✅ This incident has been resolved. Would you like to create a new incident?"
            elif incident.get('status') == 'closed':
                response += "This incident has been closed. Would you like to create a new incident?"
            
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': selected_incident_id,
                'status': incident.get('status')
            }
        
    def _handle_new_incident(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle creating a new incident"""
        # Search KB for matching entry
        kb_result = kb_service.search_kb(user_input)
        
        if kb_result['best_match']:
            return self._create_new_incident(user_input, session_id, conversation_history, kb_result)
        else:
            # Analyze if it's a technical issue
            analysis = llm_service.analyze_technical_issue(user_input, conversation_history)
            
            if analysis.get('is_technical_issue'):
                return self._create_new_incident_without_kb(user_input, session_id, conversation_history, analysis)
            else:
                # Not a technical issue - ask for clarification
                response = llm_service.generate_not_technical_issue_response(user_input, conversation_history)
                self.update_session_context(session_id, user_input, response)
                return {
                    'message': response,
                    'session_id': session_id,
                    'incident_id': None,
                    'status': None
                }
    
    def _get_pending_incidents(self, active_incident_ids: List[str]) -> List[Dict]:
        """Get pending incidents from list of IDs"""
        pending = []
        for inc_id in active_incident_ids:
            incident = mongo_client.get_incident_by_id(inc_id)
            if incident and incident.get('status') == 'pending_info':
                pending.append(incident)
        return pending
    
    def _create_new_incident(self, user_input: str, session_id: str, conversation_history: List[Dict], kb_result: Dict) -> Dict[str, Any]:
        """Create new incident with KB match"""
        try:
            best_match = kb_result['best_match']
            incident_id = generate_incident_id()
            
            default_message = self._get_default_admin_message('pending_info')
            
            incident_data = {
                'incident_id': incident_id,
                'user_demand': user_input,
                'session_id': session_id,
                'status': 'pending_info',
                'kb_id': best_match['kb_id'],
                'collected_info': {},
                'required_info': best_match['required_info'],
                'missing_info': best_match['required_info'].copy(),
                'questions': best_match['questions'],
                'solution_steps': best_match['solution_steps'],
                'conversation_history': [],
                'is_new_kb_entry': False,
                'needs_kb_approval': False,
                'requires_kb_addition': False,
                'admin_message': default_message,
                'created_on': datetime.utcnow(),
                'updated_on': datetime.utcnow()
            }
            
            mongo_client.create_incident(incident_data)
            self.add_incident_to_session(session_id, incident_id)
            
            question = llm_service.generate_kb_question(
                best_match,
                user_input,
                {},
                best_match['required_info'],
                conversation_history
            )
            
            incident_data['conversation_history'].append({'role': 'user', 'content': user_input})
            incident_data['conversation_history'].append({'role': 'assistant', 'content': question})
            mongo_client.update_incident(incident_id, {'conversation_history': incident_data['conversation_history']})
            
            self.update_session_context(session_id, user_input, question)
            
            return {
                'message': question,
                'session_id': session_id,
                'incident_id': incident_id,
                'status': 'pending_info'
            }
            
        except Exception as e:
            logger.error(f"Error creating new incident: {e}")
            return {
                'message': "I apologize, but I encountered an error creating your incident. Please try again.",
                'session_id': session_id,
                'incident_id': None,
                'status': 'error'
            }

    def _create_new_incident_without_kb(self, user_input: str, session_id: str, conversation_history: List[Dict], analysis: Dict) -> Dict[str, Any]:
        """Create new incident without KB match (needs admin approval)"""
        try:
            incident_id = generate_incident_id()
            
            required_info = analysis.get('required_info', [])
            questions = analysis.get('clarifying_questions', [])
            
            default_message = self._get_default_admin_message('pending_info')
            
            incident_data = {
                'incident_id': incident_id,
                'user_demand': user_input,
                'session_id': session_id,
                'status': 'pending_info',
                'kb_id': None,
                'collected_info': {},
                'required_info': required_info,
                'missing_info': required_info.copy(),
                'questions': questions,
                'solution_steps': '',
                'conversation_history': [],
                'is_new_kb_entry': True,
                'needs_kb_approval': True,
                'requires_kb_addition': True,
                'admin_message': default_message,
                'created_on': datetime.utcnow(),
                'updated_on': datetime.utcnow()
            }
            
            mongo_client.create_incident(incident_data)
            self.add_incident_to_session(session_id, incident_id)
            
            if questions:
                question = questions[0]
            else:
                question = f"I understand you're experiencing an issue with: {user_input}. Can you provide more details about this problem?"
            
            incident_data['conversation_history'].append({'role': 'user', 'content': user_input})
            incident_data['conversation_history'].append({'role': 'assistant', 'content': question})
            mongo_client.update_incident(incident_id, {'conversation_history': incident_data['conversation_history']})
            
            self.update_session_context(session_id, user_input, question)
            
            logger.info(f"New incident created needing KB approval: {incident_id}")
            
            return {
                'message': question,
                'session_id': session_id,
                'incident_id': incident_id,
                'status': 'pending_info'
            }
            
        except Exception as e:
            logger.error(f"Error creating new incident without KB: {e}")
            return {
                'message': "I apologize, but I encountered an error creating your incident. Please try again.",
                'session_id': session_id,
                'incident_id': None,
                'status': 'error'
            }

    def _continue_incident(self, incident: Dict, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Continue with existing pending incident"""
        try:
            incident_id = incident['incident_id']
            collected_info = incident.get('collected_info', {})
            missing_info = incident.get('missing_info', [])
            incident_conversation = incident.get('conversation_history', [])
            
            if not missing_info:
                return self._finalize_incident(incident_id, session_id, collected_info, incident_conversation, user_input)
            
            current_field = missing_info[0] if missing_info else ""
            incident_conversation.append({'role': 'user', 'content': user_input})
            
            user_lower = user_input.lower().strip()
            extracted_value = None
            is_valid = False
            
            if current_field:
                field_lower = current_field.lower()
                
                # ✅ FIX: Handle error message questions specially
                if 'error' in field_lower and ('message' in field_lower or 'code' in field_lower):
                    # Check if user is saying "no error"
                    if any(phrase in user_lower for phrase in [
                        'no error', 'no errors', 'none', 'nothing', 'not seeing', "don't see",
                        'no message', 'no code', 'nope', "doesn't show", "didnt see"
                    ]):
                        extracted_value = "No error message"
                        is_valid = True
                        logger.info(f"✅ Accepted 'no error' response: {user_input}")
                    elif len(user_input) > 5:
                        extracted_value = user_input.strip()
                        is_valid = True
                        logger.info(f"✅ Error message provided: {extracted_value}")
                
                elif 'operating system' in field_lower or 'os' in field_lower:
                    if any(os in user_lower for os in ['windows', 'mac', 'linux', 'macos', 'ubuntu', 'ios', 'android']):
                        extracted_value = user_input.strip()
                        is_valid = True
                        logger.info(f"✅ Direct OS match: {extracted_value}")
                
                elif 'vpn' in field_lower and 'client' in field_lower:
                    if any(vpn in user_lower for vpn in ['cisco', 'anyconnect', 'globalprotect', 'forticlient', 'pulse']):
                        extracted_value = user_input.strip()
                        is_valid = True
                        logger.info(f"✅ Direct VPN client match: {extracted_value}")
                
                elif 'network' in field_lower:
                    if any(net in user_lower for net in ['home', 'office', 'public', 'wifi', 'ethernet']):
                        extracted_value = user_input.strip()
                        is_valid = True
                        logger.info(f"✅ Direct network match: {extracted_value}")
                
                elif 'account' in field_lower:
                    if any(acc in user_lower for acc in ['office365', 'exchange', 'imap', 'gmail', 'outlook']):
                        extracted_value = user_input.strip()
                        is_valid = True
                        logger.info(f"✅ Account type match: {extracted_value}")
                
                elif 'email' in field_lower or 'user id' in field_lower:
                    if '@' in user_input or len(user_input) > 3:
                        extracted_value = user_input.strip()
                        is_valid = True
                        logger.info(f"✅ Email/UserID provided: {extracted_value}")
                
                elif len(user_input.split()) <= 5 and len(user_input) > 1:
                    extracted_value = user_input.strip()
                    is_valid = True
                    logger.info(f"✅ Short specific answer accepted: {extracted_value}")
            
            if is_valid and extracted_value:
                collected_info[current_field] = extracted_value
                missing_info.pop(0)
                logger.info(f"✅ Successfully collected '{current_field}': {extracted_value}")
                
                mongo_client.update_incident(incident_id, {
                    'conversation_history': incident_conversation,
                    'collected_info': collected_info,
                    'missing_info': missing_info
                })
                
                if not missing_info:
                    return self._finalize_incident(incident_id, session_id, collected_info, incident_conversation, user_input)
                
                # Generate next question
                if incident.get('kb_id'):
                    kb_entry = kb_service.get_kb_entry(incident['kb_id'])
                    if kb_entry:
                        next_question = llm_service.generate_kb_question(
                            kb_entry,
                            user_input,
                            collected_info,
                            missing_info,
                            incident_conversation
                        )
                    else:
                        next_question = f"Can you provide information about: {missing_info[0]}?"
                else:
                    questions = incident.get('questions', [])
                    questions_asked = len(collected_info)
                    
                    if questions_asked < len(questions):
                        next_question = questions[questions_asked]
                    else:
                        next_question = f"Can you provide information about: {missing_info[0]}?"
                
                incident_conversation.append({'role': 'assistant', 'content': next_question})
                mongo_client.update_incident(incident_id, {
                    'conversation_history': incident_conversation
                })
                
                self.update_session_context(session_id, user_input, next_question)
                
                return {
                    'message': next_question,
                    'session_id': session_id,
                    'incident_id': incident_id,
                    'status': 'pending_info'
                }
            
            else:
                logger.warning(f"⚠️ Invalid response for '{current_field}': {user_input}")
                
                last_question = ""
                for msg in reversed(incident_conversation):
                    if msg.get('role') == 'assistant':
                        last_question = msg.get('content', '')
                        break
                
                followup = f"I need specific information about: {current_field}. {last_question}"
                incident_conversation.append({'role': 'assistant', 'content': followup})
                
                mongo_client.update_incident(incident_id, {
                    'conversation_history': incident_conversation
                })
                
                self.update_session_context(session_id, user_input, followup)
                
                return {
                    'message': followup,
                    'session_id': session_id,
                    'incident_id': incident_id,
                    'status': 'pending_info'
                }
            
        except Exception as e:
            logger.error(f"❌ Error continuing incident: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'message': "I apologize, but I encountered an error processing your response. Please try again.",
                'session_id': session_id,
                'incident_id': incident.get('incident_id'),
                'status': 'error'
            }

    
    def _finalize_incident(self, incident_id: str, session_id: str, collected_info: Dict, conversation: List, user_input: str) -> Dict:
        """Finalize and close incident collection"""
        default_message = self._get_default_admin_message('open')
        
        final_message = llm_service.generate_incident_completion_message(incident_id)
        conversation.append({'role': 'assistant', 'content': final_message})
        
        mongo_client.update_incident(incident_id, {
            'status': 'open',
            'conversation_history': conversation,
            'collected_info': collected_info,
            'missing_info': [],
            'admin_message': default_message,
            'completed_at': datetime.utcnow()
        })
        
        self.update_session_context(session_id, user_input, final_message)
        
        return {
            'message': final_message,
            'session_id': session_id,
            'incident_id': incident_id,
            'status': 'open'
        }
    
    def _handle_ask_incident_type(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle when user says 'create incident' without describing the problem"""
        # ✅ Use LLM to generate confirmation and ask for issue type
        response = llm_service.generate_ask_incident_type_response(user_input, conversation_history)
        
        self.update_session_context(session_id, user_input, response)
        
        # ✅ Set awaiting response so next input will be treated as issue description
        mongo_client.update_session(session_id, {
            'awaiting_response': 'issue_description'
        })
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': 'awaiting_issue_description'
        }
    
    def _is_asking_about_previous_solution(self, user_input: str) -> bool:
        """Check if user is asking about a previous incident/solution"""
        keywords = ['previous', 'last', 'earlier', 'before', 'my incident', 'solution', 'what happened', 'status', 'view solution', 'continue my', 'old incident']
        user_lower = user_input.lower()
        return any(keyword in user_lower for keyword in keywords)

    def _handle_previous_solution_query(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle queries about previous solutions"""
        incident_id_match = re.search(r'INC\d+', user_input)
        
        if incident_id_match:
            incident_id = incident_id_match.group()
            incident = mongo_client.get_incident_by_id(incident_id)
            
            if incident:
                if incident.get('status') == 'pending_info':
                    response = f"I found your incident {incident_id}. Let's continue from where we left off.\n\n"
                    return self._continue_incident(incident, user_input, session_id, conversation_history)
                else:
                    incident_details = {
                        'incident_id': incident.get('incident_id'),
                        'status': incident.get('status'),
                        'user_demand': incident.get('user_demand'),
                        'collected_info': incident.get('collected_info', {}),
                        'solution_steps': incident.get('solution_steps', 'Not yet provided'),
                        'admin_message': incident.get('admin_message', '')
                    }
                    
                    response = llm_service.generate_incident_status_response(incident_details)
                    self.update_session_context(session_id, user_input, response)
                    
                    return {
                        'message': response,
                        'session_id': session_id,
                        'incident_id': incident_id,
                        'status': incident.get('status')
                    }
            else:
                response = f"I couldn't find incident {incident_id}. Please check the ID and try again."
                self.update_session_context(session_id, user_input, response)
                return {
                    'message': response,
                    'session_id': session_id,
                    'incident_id': None,
                    'status': 'not_found'
                }
        else:
            response = "I'd be happy to help you with a previous incident. Please provide the Incident ID (e.g., INC20251022150744):"
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_incident_id'
            }
        
    def _get_default_admin_message(self, status: str) -> str:
        """Get default admin message based on incident status"""
        return llm_service.generate_default_admin_message(status)

    # Admin methods
    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return mongo_client.get_incident_by_id(incident_id)
    
    def get_all_incidents(self) -> List[Dict[str, Any]]:
        incidents = mongo_client.get_all_incidents()
        logger.info(f"Retrieved {len(incidents)} incidents from database")
        
        for incident in incidents:
            if 'incident_type' not in incident:
                user_demand = incident.get('user_demand', 'IT Issue')
                if len(user_demand) > 50:
                    incident['incident_type'] = user_demand[:50] + '...'
                else:
                    incident['incident_type'] = user_demand
            
            if 'use_case' not in incident:
                incident['use_case'] = incident.get('user_demand', 'Unknown Issue')
            
            if 'needs_kb_approval' not in incident:
                incident['needs_kb_approval'] = False
            
            if 'is_new_kb_entry' not in incident:
                incident['is_new_kb_entry'] = False
            
            if 'admin_message' not in incident:
                incident['admin_message'] = ''
        
        return incidents
    
    def get_incidents_by_status(self, status: str) -> List[Dict[str, Any]]:
        incidents = mongo_client.get_incidents_by_filter({'status': status})
        for incident in incidents:
            if 'incident_type' not in incident:
                incident['incident_type'] = incident.get('user_demand', 'IT Issue')[:50] + '...' if len(incident.get('user_demand', '')) > 50 else incident.get('user_demand', 'IT Issue')
        return incidents
    
    def get_incidents_needing_approval(self) -> List[Dict[str, Any]]:
        incidents = mongo_client.get_incidents_by_filter({
            '$or': [
                {'needs_kb_approval': True},
                {'requires_kb_addition': True},
                {'is_new_kb_entry': True}
            ]
        })
        for incident in incidents:
            if 'incident_type' not in incident:
                incident['incident_type'] = incident.get('user_demand', 'IT Issue')[:50] + '...' if len(incident.get('user_demand', '')) > 50 else incident.get('user_demand', 'IT Issue')
        return incidents
    
    def update_incident_status(self, incident_id: str, status: str) -> bool:
        try:
            valid_statuses = ['pending_info', 'open', 'resolved']
            if status not in valid_statuses:
                logger.error(f"Invalid status: {status}. Valid statuses: {valid_statuses}")
                return False
            
            current_incident = mongo_client.get_incident_by_id(incident_id)
            current_admin_message = current_incident.get('admin_message', '') if current_incident else ''
            
            update_data = {'status': status}
            
            if status in ['pending_info', 'open'] and (not current_admin_message or current_admin_message in [
                'Still need some information.',
                'All information collected. Our team will contact you soon.',
                'Incident has been resolved successfully.'
            ]):
                update_data['admin_message'] = self._get_default_admin_message(status)
            elif status == 'resolved' and (not current_admin_message or current_admin_message in [
                'Still need some information.',
                'All information collected. Our team will contact you soon.',
                'Incident has been resolved successfully.'
            ]):
                update_data['admin_message'] = self._get_default_admin_message(status)
            
            if status == 'resolved':
                update_data['resolved_on'] = datetime.utcnow()
            
            success = mongo_client.update_incident(incident_id, update_data)
            
            if success:
                logger.info(f"Successfully updated incident {incident_id} status to {status}")
            else:
                logger.error(f"Failed to update incident {incident_id} status")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating incident status: {e}")
            return False
    
    def approve_kb_entry(self, incident_id: str, solution_steps: str) -> bool:
        try:
            logger.info(f"Approving KB entry for incident {incident_id}")
            
            incident = mongo_client.get_incident_by_id(incident_id)
            
            if not incident:
                logger.error(f"Incident not found: {incident_id}")
                return False
            
            update_data = {
                'solution_steps': solution_steps,
                'needs_kb_approval': False,
                'requires_kb_addition': False
            }
            
            success = mongo_client.update_incident(incident_id, update_data)
            
            if success and incident.get('is_new_kb_entry'):
                use_case = incident.get('user_demand', 'Unknown Issue')
                required_info = incident.get('required_info', [])
                
                logger.info(f"Creating new KB entry for: {use_case}")
                
                new_kb_id = kb_service.add_new_kb_entry(
                    use_case=use_case,
                    required_info=required_info,
                    solution_steps=[solution_steps],
                    questions=incident.get('questions', [])
                )
                
                if new_kb_id:
                    mongo_client.update_incident(incident_id, {
                        'kb_id': new_kb_id,
                        'is_new_kb_entry': False
                    })
                    
                    kb_service.append_to_kb_file(new_kb_id, use_case, required_info, [solution_steps])
                    logger.info(f"New KB entry created: {new_kb_id} for incident: {incident_id}")
                    return True
                else:
                    logger.error("Failed to create new KB entry")
                    return False
            else:
                return success
            
        except Exception as e:
            logger.error(f"Error approving KB entry: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

# Global incident service instance
incident_service = IncidentService()