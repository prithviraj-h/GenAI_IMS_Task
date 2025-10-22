# backend/api/admin.py
from fastapi import APIRouter, HTTPException, Query
from services.incident_service import incident_service
from services.kb_service import kb_service
from db.chroma import chroma_client
from models.schemas import KBApprovalRequest
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def get_stats():
    """Get dashboard statistics"""
    try:
        all_incidents = incident_service.get_all_incidents()
        
        stats = {
            "total": len(all_incidents),
            "pending_info": len([i for i in all_incidents if i.get('status') == 'pending_info']),
            "open": len([i for i in all_incidents if i.get('status') == 'open']),
            "resolved": len([i for i in all_incidents if i.get('status') == 'resolved']),
            "needs_kb_approval": len([i for i in all_incidents if i.get('needs_kb_approval') == True])
        }
        
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/incidents")
async def get_incidents(
    status: Optional[str] = Query(None),
    needs_kb_approval: Optional[bool] = Query(None)
):
    """Get all incidents with optional filters"""
    try:
        incidents = incident_service.get_all_incidents(status)
        
        # Filter by KB approval if requested
        if needs_kb_approval is not None:
            incidents = [inc for inc in incidents if inc.get('needs_kb_approval') == needs_kb_approval]
        
        return {
            "incidents": incidents,
            "total": len(incidents)
        }
    except Exception as e:
        logger.error(f"Error getting incidents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Get specific incident details"""
    try:
        incident = incident_service.get_incident(incident_id)
        if incident:
            return incident
        else:
            raise HTTPException(status_code=404, detail="Incident not found")
    except Exception as e:
        logger.error(f"Error getting incident: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/incidents/{incident_id}/status")
async def update_incident_status(incident_id: str, request: Dict[str, str]):
    """Update incident status (resolve, reopen, etc.)"""
    try:
        status = request.get('status')
        if not status:
            raise HTTPException(status_code=400, detail="Status is required")
        
        success = incident_service.update_incident_status(incident_id, status)
        if success:
            return {"message": f"Incident status updated to {status}", "incident_id": incident_id}
        else:
            raise HTTPException(status_code=400, detail="Failed to update incident status")
    except Exception as e:
        logger.error(f"Error updating incident status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/incidents/{incident_id}/approve-kb")
async def approve_kb_entry(incident_id: str, request: Dict[str, str]):
    """Approve incident and add to knowledge base"""
    try:
        solution_steps = request.get('solution_steps')
        if not solution_steps:
            raise HTTPException(status_code=400, detail="Solution steps are required")
        
        success = incident_service.approve_kb_entry(incident_id, solution_steps)
        
        if success:
            return {
                "message": "KB entry approved and added successfully",
                "incident_id": incident_id
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to approve KB entry")
    except Exception as e:
        logger.error(f"Error approving KB entry: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/kb/entries")
async def get_kb_entries():
    """Get all knowledge base entries"""
    try:
        entries = kb_service.get_all_kb_entries()
        return {
            "entries": entries,
            "total": len(entries)
        }
    except Exception as e:
        logger.error(f"Error getting KB entries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/chroma/entries")
async def get_chroma_entries():
    """Get all entries stored in ChromaDB (for debugging)"""
    try:
        entries = chroma_client.get_all_entries()
        return {
            "entries": entries,
            "total": len(entries),
            "note": "These are KB entries stored in ChromaDB vector database for similarity search"
        }
    except Exception as e:
        logger.error(f"Error getting ChromaDB entries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats")
async def get_stats():
    """Get dashboard statistics"""
    try:
        all_incidents = incident_service.get_all_incidents()
        
        stats = {
            "total": len(all_incidents),
            "pending_info": len([i for i in all_incidents if i.get('status') == 'pending_info']),
            "open": len([i for i in all_incidents if i.get('status') == 'open']),
            "resolved": len([i for i in all_incidents if i.get('status') == 'resolved']),
            "needs_kb_approval": len([i for i in all_incidents if i.get('needs_kb_approval') == True])
        }
        
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/incidents/{incident_id}")
async def delete_incident(incident_id: str):
    """Delete an incident (admin only)"""
    try:
        from db.mongo import mongo_client
        result = mongo_client.incidents.delete_one({'incident_id': incident_id})
        
        if result.deleted_count > 0:
            return {"message": "Incident deleted successfully", "incident_id": incident_id}
        else:
            raise HTTPException(status_code=404, detail="Incident not found")
    except Exception as e:
        logger.error(f"Error deleting incident: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")