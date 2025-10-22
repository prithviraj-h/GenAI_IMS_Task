# backend/services/incident_service.py - Enhanced version
from db.mongo import mongo_client
from services.kb_service import kb_service
from services.llm_service import llm_service
from utils.preprocessing import generate_incident_id
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import uuid

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
            'awaiting_response': None,  # Track what we're waiting for
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
            # Close all active incidents in this session
            session = mongo_client.get_session(session_id)
            if session:
                active_incidents = session.get('active_incidents', [])
                for incident_id in active_incidents:
                    self._close_incident_silently(incident_id)
            
            # Update session to clear everything
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
    
    def _close_incident_silently(self, incident_id: str):
        """Close incident without generating response"""
        try:
            mongo_client.update_incident(incident_id, {
                'status': 'closed',
                'closed_on': datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"Error closing incident silently: {e}")
    
    def update_session_context(self, session_id: str, user_input: str, assistant_response: str):
        """Update session conversation context"""
        session = mongo_client.get_session(session_id)
        if session:
            conversation_context = session.get('conversation_context', [])
            conversation_context.append({'role': 'user', 'content': user_input})
            conversation_context.append({'role': 'assistant', 'content': assistant_response})
            
            # Keep only last 50 messages
            if len(conversation_context) > 50:
                conversation_context = conversation_context[-50:]
            
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
    
    def process_user_query(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """Main method to process user query with intent detection"""
        try:
            # Get or create session
            session_id = self.get_or_create_session(session_id)
            session = mongo_client.get_session(session_id)
            
            conversation_history = session.get('conversation_context', [])
            active_incidents = session.get('active_incidents', [])
            awaiting_response = session.get('awaiting_response')
            
            has_active_incident = len(active_incidents) > 0
            
            # Detect user intent using LLM
            intent_data = llm_service.detect_intent(
                user_input, 
                conversation_history, 
                has_active_incident, 
                session_id
            )
            
            intent = intent_data.get('intent', 'GENERAL_QUERY')
            logger.info(f"Processing intent: {intent}")
            
            # Handle different intents
            if intent == 'GREETING':
                return self._handle_greeting(user_input, session_id, conversation_history)
            
            elif intent == 'CLEAR_SESSION':
                return self._handle_clear_session(session_id, conversation_history, user_input)
            
            elif intent == 'TRACK_INCIDENT':
                return self._handle_track_incident_request(user_input, session_id, conversation_history)
            elif intent == 'ASK_INCIDENT_TYPE':
                return self._handle_ask_incident_type(user_input, session_id, conversation_history)
            elif intent == 'PROVIDE_INCIDENT_ID':
                incident_id = intent_data.get('extracted_incident_id')
                return self._handle_track_incident_by_id(incident_id, user_input, session_id, conversation_history)
            
            elif intent == 'CLOSE_INCIDENT':
                return self._handle_close_incident(active_incidents, user_input, session_id, conversation_history)
            
            elif intent == 'NEW_INCIDENT':
                # Check if awaiting keep/ignore response
                if awaiting_response == 'keep_or_ignore':
                    return self._handle_keep_ignore_response(user_input, session_id, conversation_history, active_incidents)
                
                # Check if user has active pending incidents
                if has_active_incident:
                    return self._handle_new_incident_with_active(user_input, session_id, conversation_history, active_incidents)
                else:
                    return self._handle_new_incident(user_input, session_id, conversation_history)
            
            elif intent == 'CONTINUE_INCIDENT':
                # User is continuing with current incident
                pending_incidents = self._get_pending_incidents(active_incidents)
                if pending_incidents:
                    return self._continue_incident(pending_incidents[-1], user_input, session_id, conversation_history)
                else:
                    # No pending incidents, treat as new
                    return self._handle_new_incident(user_input, session_id, conversation_history)
            elif intent == 'ASK_INCIDENT_TYPE':
                return self._handle_ask_incident_type(user_input, session_id, conversation_history)
            
            else:
                # General query or fallback
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
            return {
                'message': "I apologize, but I encountered an error processing your request. Please try again.",
                'session_id': session_id,
                'incident_id': None,
                'status': 'error'
            }
    
    def _handle_greeting(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle greeting intent"""
        response = llm_service.generate_greeting_response(user_input, conversation_history)
        self.update_session_context(session_id, user_input, response)
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': None
        }
    
    def _handle_clear_session(self, session_id: str, conversation_history: List[Dict], user_input: str) -> Dict[str, Any]:
        """Handle clear session intent"""
        response = llm_service.generate_clear_session_confirmation()
        self.update_session_context(session_id, user_input, response)
        
        # Clear the session
        self.clear_session(session_id)
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': 'session_cleared',
            'action': 'clear_session'
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
        """Handle tracking incident by ID"""
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
            
            # Generate status response
            incident_details = {
                'incident_id': incident.get('incident_id'),
                'status': incident.get('status'),
                'user_demand': incident.get('user_demand'),
                'collected_info': incident.get('collected_info', {}),
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
        
        # Close the most recent active incident
        incident_id = active_incidents[-1]
        incident = mongo_client.get_incident_by_id(incident_id)
        
        if incident:
            # Mark incident as closed
            mongo_client.update_incident(incident_id, {
                'status': 'closed',
                'closed_on': datetime.utcnow()
            })
            
            # Remove from active incidents
            self.remove_incident_from_session(session_id, incident_id)
            
            # Generate confirmation
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
    
    def _handle_new_incident_with_active(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle new incident when user has active incidents"""
        # Get current incident details
        current_incident_id = active_incidents[-1]
        current_incident = mongo_client.get_incident_by_id(current_incident_id)
        current_issue = current_incident.get('user_demand', 'your current issue') if current_incident else 'your current issue'
        
        # Generate response asking to keep or ignore
        response = (f"I understand that you're also experiencing issues with: {user_input}\n\n"
                   f"I see that you currently have an active incident regarding {current_issue} ({current_incident_id}).\n\n"
                   f"Would you like to keep the previous incident open and create a new one, or ignore the previous incident and focus on this new issue?\n\n"
                   f"• **Keep:** Both incidents will remain open and be tracked in your session.\n"
                   f"• **Ignore:** The previous incident will be closed, and we'll focus on the new issue.\n\n"
                   f"Please reply with either **KEEP** or **IGNORE**.")
        
        self.update_session_context(session_id, user_input, response)
        
        # Mark that we're awaiting keep/ignore response
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
    def _handle_keep_ignore_response(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle user's response to keep or ignore previous incident"""
        user_lower = user_input.lower().strip()
        session = mongo_client.get_session(session_id)
        pending_query = session.get('pending_new_incident_query', '')
        
        # Clear awaiting response
        mongo_client.update_session(session_id, {
            'awaiting_response': None,
            'pending_new_incident_query': None
        })
        
        if 'ignore' in user_lower:
            # Close previous incidents and start fresh
            for incident_id in active_incidents:
                self._close_incident_silently(incident_id)
                self.remove_incident_from_session(session_id, incident_id)
            
            # Clear conversation history
            mongo_client.update_session(session_id, {
                'conversation_context': []
            })
            
            # Process new incident
            return self._handle_new_incident(pending_query if pending_query else user_input, session_id, [])
        
        elif 'keep' in user_lower:
            # Keep existing incidents and create new one
            return self._handle_new_incident(pending_query if pending_query else user_input, session_id, conversation_history)
        
        else:
            # User didn't say keep or ignore - ask again
            response = "I'm sorry, I didn't understand. Please reply with:\n\n**KEEP** - to keep the previous incident open\n**IGNORE** - to close the previous incident and focus on the new issue"
            self.update_session_context(session_id, user_input, response)
            
            # Restore awaiting response state
            mongo_client.update_session(session_id, {
                'awaiting_response': 'keep_or_ignore',
                'pending_new_incident_query': pending_query
            })
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_decision'
            }
        
    def _handle_new_incident(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle creating a new incident"""
        # Search KB
        kb_result = kb_service.search_kb(user_input)
        
        if kb_result['best_match']:
            # Found matching KB entry
            return self._create_new_incident(user_input, session_id, conversation_history, kb_result)
        else:
            # No KB match - analyze with LLM
            analysis = llm_service.analyze_technical_issue(user_input, conversation_history)
            
            if analysis.get('is_technical_issue'):
                # New technical issue without KB match - needs admin approval
                return self._create_new_incident_without_kb(user_input, session_id, conversation_history, analysis)
            else:
                # Not a technical issue
                response = llm_service.handle_general_query(user_input, conversation_history)
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
    
    def _create_new_incident(self, user_input: str, session_id: str,
                            conversation_history: List[Dict], kb_result: Dict) -> Dict[str, Any]:
        """Create new incident with KB match"""
        try:
            best_match = kb_result['best_match']
            incident_id = generate_incident_id()
            
            # Create incident
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
                'created_on': datetime.utcnow(),
                'updated_on': datetime.utcnow()
            }
            
            mongo_client.create_incident(incident_data)
            self.add_incident_to_session(session_id, incident_id)
            
            # Generate first question
            question = llm_service.generate_kb_question(
                best_match,
                user_input,
                {},
                best_match['required_info'],
                conversation_history
            )
            
            # Update incident with first question
            incident_data['conversation_history'].append({'role': 'user', 'content': user_input})
            incident_data['conversation_history'].append({'role': 'assistant', 'content': question})
            mongo_client.update_incident(incident_id, {'conversation_history': incident_data['conversation_history']})
            
            # Update session context
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
    
    def _create_new_incident_without_kb(self, user_input: str, session_id: str,
                                       conversation_history: List[Dict], analysis: Dict) -> Dict[str, Any]:
        """Create new incident without KB match (needs admin approval)"""
        try:
            incident_id = generate_incident_id()
            
            required_info = analysis.get('required_info', [])
            questions = analysis.get('clarifying_questions', [])
            
            # Create incident
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
                'created_on': datetime.utcnow(),
                'updated_on': datetime.utcnow()
            }
            
            mongo_client.create_incident(incident_data)
            self.add_incident_to_session(session_id, incident_id)
            
            # Generate first question using LLM
            if questions:
                question = questions[0]
            else:
                question = f"I understand you're experiencing an issue with: {user_input}. Can you provide more details about this problem?"
            
            # Update incident with first question
            incident_data['conversation_history'].append({'role': 'user', 'content': user_input})
            incident_data['conversation_history'].append({'role': 'assistant', 'content': question})
            mongo_client.update_incident(incident_id, {'conversation_history': incident_data['conversation_history']})
            
            # Update session context
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
            
            last_question = ""
            if incident_conversation:
                for msg in reversed(incident_conversation):
                    if msg['role'] == 'assistant':
                        last_question = msg['content']
                        break
            
            current_field = missing_info[0] if missing_info else ""
            
            extraction = llm_service.extract_info_from_response(user_input, last_question, current_field)
            
            incident_conversation.append({'role': 'user', 'content': user_input})
            
            if extraction.get('is_relevant') and extraction.get('answers_question'):
                if missing_info:
                    current_field = missing_info[0]
                    extracted_value = extraction.get('extracted_info', user_input)
                    
                    if extracted_value and extracted_value.strip():
                        collected_info[current_field] = extracted_value.strip()
                        missing_info.pop(0)
                        logger.info(f"Collected info for '{current_field}': {extracted_value}")
                    else:
                        followup = f"I appreciate your response, but I need specific information about: {current_field}. Let me ask again: {last_question}"
                        incident_conversation.append({'role': 'assistant', 'content': followup})
                        
                        mongo_client.update_incident(incident_id, {
                            'conversation_history': incident_conversation,
                            'collected_info': collected_info
                        })
                        
                        self.update_session_context(session_id, user_input, followup)
                        
                        return {
                            'message': followup,
                            'session_id': session_id,
                            'incident_id': incident_id,
                            'status': 'pending_info'
                        }
            else:
                if current_field:
                    followup = f"I appreciate your response. However, I need specific information about: {current_field}. Let me ask again: {last_question}"
                else:
                    followup = f"I appreciate your response. However, I need more specific information. Let me ask again: {last_question}"
                
                incident_conversation.append({'role': 'assistant', 'content': followup})
                
                mongo_client.update_incident(incident_id, {
                    'conversation_history': incident_conversation,
                    'collected_info': collected_info
                })
                
                self.update_session_context(session_id, user_input, followup)
                
                return {
                    'message': followup,
                    'session_id': session_id,
                    'incident_id': incident_id,
                    'status': 'pending_info'
                }
            
            if not missing_info:
                return self._finalize_incident(incident_id, session_id, collected_info, incident_conversation, user_input)
            else:
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
                    'conversation_history': incident_conversation,
                    'collected_info': collected_info,
                    'missing_info': missing_info
                })
                
                self.update_session_context(session_id, user_input, next_question)
                
                return {
                    'message': next_question,
                    'session_id': session_id,
                    'incident_id': incident_id,
                    'status': 'pending_info'
                }
            
        except Exception as e:
            logger.error(f"Error continuing incident: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'message': "I apologize, but I encountered an error processing your response. Please try again.",
                'session_id': session_id,
                'incident_id': incident.get('incident_id'),
                'status': 'error'
            }
    
    def _finalize_incident(self, incident_id: str, session_id: str, collected_info: Dict,
                          conversation: List, user_input: str) -> Dict:
        """Finalize and close incident collection"""
        final_message = (f"Thank you for providing all the necessary information. "
                        f"Your incident has been created successfully.\n\n"
                        f"Incident ID: {incident_id}\n\n"
                        f"Our IT team will review your issue and get back to you soon.")
        
        conversation.append({'role': 'assistant', 'content': final_message})
        
        mongo_client.update_incident(incident_id, {
            'status': 'open',
            'conversation_history': conversation,
            'collected_info': collected_info,
            'missing_info': [],
            'completed_at': datetime.utcnow()
        })
        
        self.update_session_context(session_id, user_input, final_message)
        
        return {
            'message': final_message,
            'session_id': session_id,
            'incident_id': incident_id,
            'status': 'open'
        }
    
    # ========== ADMIN METHODS ==========
    
    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Get incident by ID"""
        return mongo_client.get_incident_by_id(incident_id)
    
    def get_all_incidents(self) -> List[Dict[str, Any]]:
        """Get all incidents"""
        incidents = mongo_client.get_all_incidents()
        for incident in incidents:
            if 'incident_type' not in incident:
                incident['incident_type'] = incident.get('user_demand', 'IT Issue')[:50] + '...' if len(incident.get('user_demand', '')) > 50 else incident.get('user_demand', 'IT Issue')
        return incidents
    
    def get_incidents_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get incidents by status"""
        incidents = mongo_client.get_incidents_by_filter({'status': status})
        for incident in incidents:
            if 'incident_type' not in incident:
                incident['incident_type'] = incident.get('user_demand', 'IT Issue')[:50] + '...' if len(incident.get('user_demand', '')) > 50 else incident.get('user_demand', 'IT Issue')
        return incidents
    
    def get_incidents_needing_approval(self) -> List[Dict[str, Any]]:
        """Get incidents needing KB approval"""
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
    
    def resolve_incident(self, incident_id: str, solution_steps: list = None, resolution_notes: str = None) -> bool:
        """Mark incident as resolved with solution steps"""
        try:
            update_data = {
                'status': 'resolved',
                'resolved_on': datetime.utcnow()
            }
            
            if solution_steps:
                solution_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(solution_steps)])
                update_data['solution_provided'] = solution_text
            
            if resolution_notes:
                update_data['resolution_notes'] = resolution_notes
            
            return mongo_client.update_incident(incident_id, update_data)
        except Exception as e:
            logger.error(f"Error resolving incident: {e}")
            return False
    
    def add_incident_to_kb(self, incident_id: str, use_case: str, required_info: list, solution_steps: list) -> bool:
        """Add incident type to knowledge base and kb_data.txt file"""
        try:
            incident = mongo_client.get_incident_by_id(incident_id)
            
            if not incident:
                logger.error(f"Incident not found: {incident_id}")
                return False
            
            logger.info(f"Adding incident {incident_id} to KB with use case: {use_case}")
            
            # Create KB entry
            kb_id = kb_service.add_new_kb_entry(
                use_case=use_case,
                required_info=required_info,
                solution_steps=solution_steps
            )
            
            if kb_id:
                # Update incident
                update_data = {
                    'requires_kb_addition': False,
                    'needs_kb_approval': False,
                    'is_new_kb_entry': False,
                    'kb_id': kb_id,
                    'incident_type': use_case
                }
                
                success = mongo_client.update_incident(incident_id, update_data)
                
                if success:
                    # Append to kb_data.txt file
                    kb_service.append_to_kb_file(kb_id, use_case, required_info, solution_steps)
                    logger.info(f"Successfully added incident {incident_id} to KB as {kb_id}")
                    return True
                else:
                    logger.error(f"Failed to update incident {incident_id} after KB creation")
                    return False
            else:
                logger.error(f"Failed to create KB entry for incident {incident_id}")
                return False
            
        except Exception as e:
            logger.error(f"Error adding incident to KB: {e}")
            return False
    
    def approve_kb_and_add_solution(self, incident_id: str, solution_steps: str) -> bool:
        """Approve KB entry and add solution steps"""
        try:
            incident = mongo_client.get_incident_by_id(incident_id)
            
            if not incident:
                logger.error(f"Incident not found: {incident_id}")
                return False
            
            logger.info(f"Approving incident {incident_id} with solution: {solution_steps}")
            
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
                    
                    # Append to kb_data.txt file
                    kb_service.append_to_kb_file(new_kb_id, use_case, required_info, [solution_steps])
                    logger.info(f"New KB entry created: {new_kb_id} for incident: {incident_id}")
                    return True
                else:
                    logger.error("Failed to create new KB entry")
                    return False
            else:
                return success
            
        except Exception as e:
            logger.error(f"Error approving KB and adding solution: {e}")
            return False
    
    def _handle_ask_incident_type(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle when user says 'create incident' without describing the problem"""
        response = "I'd be happy to help you create an incident. Could you please describe the technical issue you're experiencing? For example:\n\n" \
                "- Is it related to email (Outlook)?\n" \
                "- Network connectivity (VPN, WiFi)?\n" \
                "- Software installation?\n" \
                "- Password reset?\n" \
                "- System performance?\n\n" \
                "Please tell me what problem you're facing."
        
        self.update_session_context(session_id, user_input, response)
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': 'awaiting_issue_description'
        }
    def _handle_ask_incident_type(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle when user says 'create incident' without describing the problem"""
        response = llm_service.generate_ask_incident_type_response()
        self.update_session_context(session_id, user_input, response)
        
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': None,
            'status': 'awaiting_issue_description'
        }

# Global incident service instance
incident_service = IncidentService()