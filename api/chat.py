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
        
        return IncidentResponse(
            message=result['message'],
            incident_id=result.get('incident_id'),
            session_id=result['session_id'],
            status=result.get('status'),
            action=result.get('action')
        )
        
    except Exception as e:
        logger.error(f"Error in process_query: {e}")
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
