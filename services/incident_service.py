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
        """Update session conversation context - keep only last 10 messages (5 pairs)"""
        session = mongo_client.get_session(session_id)
        if session:
            conversation_context = session.get('conversation_context', [])
            conversation_context.append({'role': 'user', 'content': user_input})
            conversation_context.append({'role': 'assistant', 'content': assistant_response})
            
            # ✅ FIX: Keep only last 10 messages (5 user + 5 assistant)
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
    
    def process_user_query(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """Main method to process user query with intent detection"""
        try:
            # Get or create session
            session_id = self.get_or_create_session(session_id)
            session = mongo_client.get_session(session_id)
            
            # ✅ FIX: Maintain only last 5 messages (context memory)
            conversation_history = session.get('conversation_context', [])
            if len(conversation_history) > 10:  # Keep last 10 (5 user + 5 assistant)
                conversation_history = conversation_history[-10:]
                mongo_client.update_session(session_id, {
                    'conversation_context': conversation_history
                })
            
            active_incidents = session.get('active_incidents', [])
            awaiting_response = session.get('awaiting_response')
            
            has_active_incident = len(active_incidents) > 0
            
            # ✅ NEW: Handle previous solution ID response
            if awaiting_response == 'previous_solution_id':
                return self._handle_previous_solution_id(user_input, session_id, conversation_history, active_incidents)
            
            # ✅ NEW: Handle incident ID selection after KEEP
            if awaiting_response == 'incident_id_selection':
                return self._handle_incident_selection(user_input, session_id, conversation_history, active_incidents)
            
            # Handle keep/ignore response
            if awaiting_response == 'keep_or_ignore':
                return self._handle_keep_ignore_response(user_input, session_id, conversation_history, active_incidents)
            
            # ✅ NEW: Check if user is asking about previous solution/incident
            if self._is_asking_about_previous_solution(user_input):
                return self._handle_previous_solution_query(user_input, session_id, conversation_history)
            
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
            
            elif intent == 'PROVIDE_INCIDENT_ID':
                incident_id = intent_data.get('extracted_incident_id')
                return self._handle_track_incident_by_id(incident_id, user_input, session_id, conversation_history)
            
            elif intent == 'CLOSE_INCIDENT':
                return self._handle_close_incident(active_incidents, user_input, session_id, conversation_history)
            
            elif intent == 'ASK_PREVIOUS_SOLUTION':
                return self._handle_ask_previous_solution(user_input, session_id, conversation_history)
            
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
        response = "Hi there! 👋 Welcome to the IT helpdesk. I'm here to assist you. How may I help you? Do you want to track an already created incident or create a new one?"
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
                {'label': 'View Previous Solution', 'value': 'view previous solution'}
            ]
        }
    
    def _handle_greeting_context(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle greeting while there's an active incident"""
        if active_incidents:
            current_incident_id = active_incidents[-1]
            current_incident = mongo_client.get_incident_by_id(current_incident_id)
            
            if current_incident and current_incident.get('status') == 'pending_info':
                # Get the last question that was asked
                incident_conversation = current_incident.get('conversation_history', [])
                last_question = ""
                for msg in reversed(incident_conversation):
                    if msg.get('role') == 'assistant':
                        last_question = msg.get('content', '')
                        break
                
                response = f"Hello! 👋 Thanks for getting back. Let's continue with your incident.\n\n{last_question}"
            else:
                response = "Hello! 👋 How can I help you further?"
        else:
            response = "Hello! 👋 How can I help you today?"
        
        self.update_session_context(session_id, user_input, response)
        return {
            'message': response,
            'session_id': session_id,
            'incident_id': current_incident_id if active_incidents else None,
            'status': 'pending_info' if active_incidents else None
        }
    
    def _handle_unrelated_query(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle unrelated query during active incident"""
        if active_incidents:
            current_incident_id = active_incidents[-1]
            current_incident = mongo_client.get_incident_by_id(current_incident_id)
            
            if current_incident and current_incident.get('status') == 'pending_info':
                # Get the last question that was asked
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
        # Clear the session first
        self.clear_session(session_id)
        
        # Generate the exact same greeting as initial greeting
        response = "Hi there! 👋 Welcome to the IT helpdesk. I'm here to assist you. How may I help you? Do you want to track an already created incident or create a new one?"
        
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
                {'label': 'View Previous Solution', 'value': 'view previous solution'}
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
    
    # Update the _handle_track_incident_by_id method to include admin message prominently
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
            
            # Get admin message - use default if empty
            admin_message = incident.get('admin_message', '')
            if not admin_message:
                admin_message = self._get_default_admin_message(incident.get('status', ''))
            
            # Generate status response with prominent admin message
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
    
    def _handle_ask_previous_solution(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle request to view previous solution or continue incident"""
        response = "I'd be happy to help you with a previous incident. Please provide the Incident ID (e.g., INC20251022150744) for which you'd like to view the solution or continue the conversation."
        self.update_session_context(session_id, user_input, response)
        
        # Mark that we're awaiting incident ID for previous solution
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
        """Handle incident ID provided for previous solution request"""
        # Extract incident ID from user input
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
        
        # Check if incident exists
        incident = mongo_client.get_incident_by_id(incident_id)
        
        if not incident:
            response = f"No previous incident found for ID: {incident_id}. Please check the ID and try again."
            self.update_session_context(session_id, user_input, response)
            
            # Clear awaiting state
            mongo_client.update_session(session_id, {
                'awaiting_response': None
            })
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'incident_not_found'
            }
        
        # Clear awaiting state
        mongo_client.update_session(session_id, {
            'awaiting_response': None
        })
        
        # If incident is resolved, show solution
        if incident.get('status') == 'resolved':
            solution_steps = incident.get('solution_steps', 'No solution steps provided yet.')
            admin_message = incident.get('admin_message', '')
            
            response = f"**Incident {incident_id} - Solution Details**\n\n"
            response += f"**Issue:** {incident.get('user_demand', 'Unknown issue')}\n\n"
            response += f"**Solution:**\n{solution_steps}\n\n"
            
            if admin_message:
                response += f"**Admin Note:** {admin_message}\n\n"
            
            response += "Is there anything else I can help you with?"
            
            self.update_session_context(session_id, user_input, response)
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': incident_id,
                'status': 'solution_displayed'
            }
        else:
            # Incident is not resolved, continue from where it stopped
            response = f"Continuing with incident {incident_id}. Let's pick up from where we left off.\n\n"
            return self._continue_incident(incident, user_input, session_id, conversation_history)
    
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
        
        if 'ignore' in user_lower:
            # Close previous incidents and CLEAR SESSION HISTORY
            for incident_id in active_incidents:
                self._close_incident_silently(incident_id)
                self.remove_incident_from_session(session_id, incident_id)
            
            # Clear conversation history completely
            mongo_client.update_session(session_id, {
                'conversation_context': [],
                'pending_new_incident_query': None,
                'awaiting_response': None
            })
            
            # Process new incident with EMPTY conversation history
            return self._handle_new_incident(pending_query if pending_query else user_input, session_id, [])
        
        elif 'keep' in user_lower:
            # ✅ FIX: Create the new incident first, then ask which one to discuss
            
            # 1. Create the new incident
            kb_result = kb_service.search_kb(pending_query)
            new_incident_id = None
            
            if kb_result['best_match']:
                # Create new incident with KB match
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
                    'admin_message': '',  # Add empty admin message field
                    'created_on': datetime.utcnow(),
                    'updated_on': datetime.utcnow()
                }
                
                mongo_client.create_incident(incident_data)
                self.add_incident_to_session(session_id, new_incident_id)
                
            else:
                # Create new incident without KB match
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
                        'admin_message': '',  # Add empty admin message field
                        'created_on': datetime.utcnow(),
                        'updated_on': datetime.utcnow()
                    }
                    
                    mongo_client.create_incident(incident_data)
                    self.add_incident_to_session(session_id, new_incident_id)
            
            # 2. Get updated list of active incidents (now includes the new one)
            updated_session = mongo_client.get_session(session_id)
            all_incidents = updated_session.get('active_incidents', [])
            
            # 3. Build incident list with descriptions
            incident_details = []
            for inc_id in all_incidents:
                inc = mongo_client.get_incident_by_id(inc_id)
                if inc:
                    issue_desc = inc.get('user_demand', 'Unknown issue')[:60]
                    incident_details.append(f"• **{inc_id}** - {issue_desc}")
            
            incidents_list = "\n".join(incident_details)
            
            # 4. Ask which incident to discuss
            response = (f"✅ Both incidents are now active and being tracked.\n\n"
                    f"**Your Active Incidents:**\n{incidents_list}\n\n"
                    f"Please provide the **Incident ID** you want to discuss:\n"
                    f"(Example: {all_incidents[0] if all_incidents else 'INC20251022150744'})")
            
            self.update_session_context(session_id, user_input, response)
            
            # Store state that we're waiting for incident ID selection
            mongo_client.update_session(session_id, {
                'awaiting_response': 'incident_id_selection',
                'pending_new_incident_query': None  # Clear since we created it
            })
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_incident_selection',
                'show_action_buttons': False
            }
        
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
                'status': 'awaiting_decision',
                'show_action_buttons': True,
                'action_buttons': [
                    {'label': 'KEEP', 'value': 'keep'},
                    {'label': 'IGNORE', 'value': 'ignore'}
                ]
            }

    def _handle_incident_selection(self, user_input: str, session_id: str, conversation_history: List[Dict], active_incidents: List[str]) -> Dict[str, Any]:
        """Handle incident ID selection after user chose KEEP"""
        
        # Extract incident ID from user input
        incident_id_match = re.search(r'INC\d+', user_input)
        
        if not incident_id_match:
            # Build incident list again for retry
            incident_details = []
            for inc_id in active_incidents:
                inc = mongo_client.get_incident_by_id(inc_id)
                if inc:
                    issue_desc = inc.get('user_demand', 'Unknown issue')[:60]
                    incident_details.append(f"• **{inc_id}** - {issue_desc}")
            
            incidents_list = "\n".join(incident_details)
            
            response = (f"I couldn't find a valid Incident ID in your message.\n\n"
                    f"**Your Active Incidents:**\n{incidents_list}\n\n"
                    f"Please provide the Incident ID (e.g., {active_incidents[0] if active_incidents else 'INC20251022150744'}):")
            
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_incident_selection'
            }
        
        selected_incident_id = incident_id_match.group()
        
        # Check if this incident exists
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
        
        # Clear awaiting state
        mongo_client.update_session(session_id, {
            'awaiting_response': None
        })
        
        # Continue with the selected incident
        if incident.get('status') == 'pending_info':
            # Continue gathering information from where it stopped
            response_prefix = f"📋 Continuing with **{selected_incident_id}** - {incident.get('user_demand', 'your issue')}\n\n"
            
            # Get the last question asked
            incident_conversation = incident.get('conversation_history', [])
            missing_info = incident.get('missing_info', [])
            
            if incident_conversation:
                # Find last assistant message
                last_question = ""
                for msg in reversed(incident_conversation):
                    if msg.get('role') == 'assistant':
                        last_question = msg.get('content', '')
                        break
                
                if last_question:
                    response = response_prefix + last_question
                else:
                    # Generate new question
                    if missing_info:
                        response = response_prefix + f"Can you provide information about: {missing_info[0]}?"
                    else:
                        response = response_prefix + "Can you provide more details about this issue?"
            else:
                # No conversation history, ask first question
                if missing_info:
                    response = response_prefix + f"Can you provide information about: {missing_info[0]}?"
                else:
                    response = response_prefix + "Can you provide more details about this issue?"
            
            self.update_session_context(session_id, user_input, response)
            
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': selected_incident_id,
                'status': 'pending_info'
            }
        else:
            # Incident is not pending info
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
    
    def _create_new_incident(self, user_input: str, session_id: str, conversation_history: List[Dict], kb_result: Dict) -> Dict[str, Any]:
        """Create new incident with KB match"""
        try:
            best_match = kb_result['best_match']
            incident_id = generate_incident_id()
            
            # Get default admin message for new incident
            default_message = self._get_default_admin_message('pending_info')
            
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
                'admin_message': default_message,  # Set default message
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
    def _create_new_incident_without_kb(self, user_input: str, session_id: str, conversation_history: List[Dict], analysis: Dict) -> Dict[str, Any]:
        """Create new incident without KB match (needs admin approval)"""
        try:
            incident_id = generate_incident_id()
            
            required_info = analysis.get('required_info', [])
            questions = analysis.get('clarifying_questions', [])
            
            # Get default admin message for new incident
            default_message = self._get_default_admin_message('pending_info')
            
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
                'admin_message': default_message,  # Set default message
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
    
    def _finalize_incident(self, incident_id: str, session_id: str, collected_info: Dict, conversation: List, user_input: str) -> Dict:
        """Finalize and close incident collection"""
        # Get default message for open status
        default_message = self._get_default_admin_message('open')
        
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
            'admin_message': default_message,  # Update to open status message
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
        """Get all incidents sorted by creation date (newest first)"""
        incidents = mongo_client.get_all_incidents()
        logger.info(f"Retrieved {len(incidents)} incidents from database")
        
        for incident in incidents:
            # Ensure incident_type field exists for display
            if 'incident_type' not in incident:
                user_demand = incident.get('user_demand', 'IT Issue')
                if len(user_demand) > 50:
                    incident['incident_type'] = user_demand[:50] + '...'
                else:
                    incident['incident_type'] = user_demand
            
            # Ensure use_case field exists (for admin dashboard)
            if 'use_case' not in incident:
                incident['use_case'] = incident.get('user_demand', 'Unknown Issue')
            
            # Ensure needs_kb_approval field exists
            if 'needs_kb_approval' not in incident:
                incident['needs_kb_approval'] = False
            
            # Ensure is_new_kb_entry field exists  
            if 'is_new_kb_entry' not in incident:
                incident['is_new_kb_entry'] = False
            
            # Ensure admin_message field exists
            if 'admin_message' not in incident:
                incident['admin_message'] = ''
        
        # Return as-is (already sorted by MongoDB)
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
    
    # ✅ ADD MISSING METHOD: update_incident_status
    def update_incident_status(self, incident_id: str, status: str) -> bool:
        """Update incident status and set appropriate admin message"""
        try:
            valid_statuses = ['pending_info', 'open', 'resolved', 'closed']
            if status not in valid_statuses:
                logger.error(f"Invalid status: {status}. Valid statuses: {valid_statuses}")
                return False
            
            # Get the current incident to check if we should preserve custom messages
            current_incident = mongo_client.get_incident_by_id(incident_id)
            current_admin_message = current_incident.get('admin_message', '') if current_incident else ''
            
            update_data = {'status': status}
            
            # Only set default message for pending_info and open if no custom message exists
            if status in ['pending_info', 'open'] and (not current_admin_message or current_admin_message in [
                'Still need some information.',
                'All information collected. Our team will contact you soon.',
                'Incident has been resolved successfully.',
                'Incident has been closed.'
            ]):
                update_data['admin_message'] = self._get_default_admin_message(status)
            elif status in ['resolved', 'closed'] and (not current_admin_message or current_admin_message in [
                'Still need some information.',
                'All information collected. Our team will contact you soon.',
                'Incident has been resolved successfully.',
                'Incident has been closed.'
            ]):
                # For resolved/closed, set default but allow admin to customize later
                update_data['admin_message'] = self._get_default_admin_message(status)
            
            # Add timestamp for resolved/closed status
            if status in ['resolved', 'closed']:
                update_data[f'{status}_on'] = datetime.utcnow()
            
            success = mongo_client.update_incident(incident_id, update_data)
            
            if success:
                logger.info(f"Successfully updated incident {incident_id} status to {status}")
            else:
                logger.error(f"Failed to update incident {incident_id} status")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating incident status: {e}")
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
    
    def approve_kb_entry(self, incident_id: str, solution_steps: str) -> bool:
        """
        Approve KB entry and add solution steps
        This is a wrapper method for approve_kb_and_add_solution
        """
        try:
            logger.info(f"Approving KB entry for incident {incident_id}")
            
            # Call the existing method with the same functionality
            return self.approve_kb_and_add_solution(incident_id, solution_steps)
            
        except Exception as e:
            logger.error(f"Error approving KB entry: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
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
    
    # ✅ NEW METHOD: Check if user is asking about previous solution
    def _is_asking_about_previous_solution(self, user_input: str) -> bool:
        """Check if user is asking about a previous incident/solution"""
        keywords = ['previous', 'last', 'earlier', 'before', 'my incident', 'solution', 'what happened', 'status', 'view solution', 'continue my', 'old incident']
        user_lower = user_input.lower()
        return any(keyword in user_lower for keyword in keywords)

    # ✅ NEW METHOD: Handle previous solution queries
    def _handle_previous_solution_query(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Handle queries about previous solutions"""
        # Check if user mentioned incident ID
        incident_id_match = re.search(r'INC\d+', user_input)
        
        if incident_id_match:
            incident_id = incident_id_match.group()
            incident = mongo_client.get_incident_by_id(incident_id)
            
            if incident:
                # Continue from where it stopped
                if incident.get('status') == 'pending_info':
                    response = f"I found your incident {incident_id}. Let's continue from where we left off.\n\n"
                    return self._continue_incident(incident, user_input, session_id, conversation_history)
                else:
                    # Show incident details
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
            # Ask for incident ID
            response = "I'd be happy to help you with a previous incident. Please provide the Incident ID (e.g., INC20251022150744):"
            self.update_session_context(session_id, user_input, response)
            return {
                'message': response,
                'session_id': session_id,
                'incident_id': None,
                'status': 'awaiting_incident_id'
            }
        
    # Add this method to the IncidentService class
    def _get_default_admin_message(self, status: str) -> str:
        """Get default admin message based on incident status"""
        default_messages = {
            'pending_info': 'Still need some information.',
            'open': 'All information collected. Our team will contact you soon.',
            'resolved': 'Incident has been resolved successfully.',
            #'closed': 'Incident has been closed.'
        }
        return default_messages.get(status, '')


# Global incident service instance
incident_service = IncidentService()