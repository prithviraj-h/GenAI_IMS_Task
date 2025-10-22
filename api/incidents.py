# backend/api/incident.py
from fastapi import APIRouter, HTTPException, Query
from services.incident_service import incident_service
from models.schemas import StatusUpdateRequest
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/incidents")
async def get_incidents(status: Optional[str] = Query(None)):
    """Get all incidents with optional status filter"""
    try:
        incidents = incident_service.get_all_incidents(status)
        return {
            "incidents": incidents,
            "total": len(incidents)
        }
    except Exception as e:
        logger.error(f"Error getting incidents: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Get specific incident by ID"""
    try:
        incident = incident_service.get_incident(incident_id)
        if incident:
            return incident
        else:
            raise HTTPException(status_code=404, detail="Incident not found")
    except Exception as e:
        logger.error(f"Error getting incident: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/incidents/{incident_id}/status")
async def update_incident_status(incident_id: str, status_update: StatusUpdateRequest):
    """Update incident status"""
    try:
        success = incident_service.update_incident_status(incident_id, status_update.status)
        if success:
            return {
                "message": f"Incident status updated to {status_update.status}",
                "incident_id": incident_id
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to update incident status")
    except Exception as e:
        logger.error(f"Error updating incident status: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")