# backend/api/chat.py
from fastapi import APIRouter, HTTPException
from models.schemas import UserQuery, IncidentResponse
from services.incident_service import incident_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.post("/query", response_model=IncidentResponse)
async def process_query(query: UserQuery):
    """
    Process user query and return response
    """
    try:
        result = incident_service.process_user_query(
            query.user_input,
            query.session_id
        )
        
        # Ensure all fields are present
        response_data = {
            'message': result.get('message', ''),
            'incident_id': result.get('incident_id'),
            'session_id': result.get('session_id', ''),
            'status': result.get('status'),
            'action': result.get('action'),
            'show_action_buttons': result.get('show_action_buttons', False),
            'action_buttons': result.get('action_buttons', None)
        }
        
        logger.info(f"Sending response with buttons: {response_data.get('show_action_buttons')}")
        if response_data.get('action_buttons'):
            logger.info(f"Button data: {response_data.get('action_buttons')}")
        
        return IncidentResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error in process_query: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    """
    Get conversation history for a session
    """
    try:
        history = incident_service.get_session_history(session_id)
        
        return {
            "session_id": session_id,
            "history": history,
            "count": len(history)
        }
        
    except Exception as e:
        logger.error(f"Error getting session history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/session/{session_id}/clear")
async def clear_session(session_id: str):
    """
    Clear session history
    """
    try:
        success = incident_service.clear_session(session_id)
        
        if success:
            return {
                "message": "Session cleared successfully",
                "session_id": session_id
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to clear session")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")