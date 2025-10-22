# backend/api/admin.py - FIXED VERSION
from fastapi import APIRouter, HTTPException, Query
from services.incident_service import incident_service
from services.kb_service import kb_service
from db.chroma import chroma_client
from models.schemas import KBApprovalRequest
from typing import Optional, List, Dict, Any
import logging
import os
from datetime import datetime  # Add this import
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
        
        logger.info(f"Stats calculated: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# backend/api/admin.py - Update get_incidents method

@router.get("/incidents")
async def get_incidents(
    status: Optional[str] = Query(None),
    needs_kb_approval: Optional[bool] = Query(None)
):
    """Get all incidents with optional filters - newest first"""
    try:
        # Get all incidents (already sorted by MongoDB)
        incidents = incident_service.get_all_incidents()
        logger.info(f"Total incidents found: {len(incidents)}")
        
        # Apply status filter if provided
        if status:
            incidents = [inc for inc in incidents if inc.get('status') == status]
            logger.info(f"After status filter '{status}': {len(incidents)} incidents")
        
        # Filter by KB approval if requested
        if needs_kb_approval is not None:
            incidents = [inc for inc in incidents if inc.get('needs_kb_approval') == needs_kb_approval]
            logger.info(f"After KB approval filter '{needs_kb_approval}': {len(incidents)} incidents")
        
        # Add use_case field for display if missing
        for incident in incidents:
            if 'use_case' not in incident:
                incident['use_case'] = incident.get('user_demand', 'Unknown Issue')
        
        # Double-check sorting by created_on (newest first)
        incidents.sort(key=lambda x: x.get('created_on', ''), reverse=True)
        
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
    """Get specific incident details"""
    try:
        incident = incident_service.get_incident(incident_id)
        if incident:
            # Ensure use_case field exists
            if 'use_case' not in incident:
                incident['use_case'] = incident.get('user_demand', 'Unknown Issue')
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

@router.delete("/incidents/{incident_id}")
async def delete_incident(incident_id: str):
    """Delete an incident (admin only)"""
    try:
        from db.mongo import mongo_client
        result = mongo_client.incidents_collection.delete_one({'incident_id': incident_id})
        
        if result.deleted_count > 0:
            return {"message": "Incident deleted successfully", "incident_id": incident_id}
        else:
            raise HTTPException(status_code=404, detail="Incident not found")
    except Exception as e:
        logger.error(f"Error deleting incident: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@router.get("/chroma/entries-with-embeddings")
async def get_chroma_entries_with_embeddings():
    """Get all ChromaDB entries WITH embeddings/vectors"""
    try:
        # Get the raw collection data including embeddings
        collection = chroma_client.collection
        results = collection.get(include=['embeddings', 'documents', 'metadatas'])
        
        entries = []
        if results and results['ids']:
            for i in range(len(results['ids'])):
                entry = {
                    'id': results['ids'][i],
                    'document': results['documents'][i],
                    'metadata': results['metadatas'][i],
                    'embedding_sample': results['embeddings'][i][:5] if results['embeddings'] else None,  # First 5 dimensions
                    'embedding_length': len(results['embeddings'][i]) if results['embeddings'] else 0
                }
                entries.append(entry)
        
        return {
            "entries": entries,
            "total": len(entries),
            "note": "Includes first 5 dimensions of each embedding vector"
        }
    except Exception as e:
        logger.error(f"Error getting ChromaDB entries with embeddings: {e}")
        return {"error": str(e)}
    
# Add to backend/api/admin.py
@router.get("/debug/kb-file-status")
async def debug_kb_file_status():
    """Check KB file status and location"""
    try:
        import os
        
        # Check current KB file path
        kb_file_path = kb_service.kb_file_path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check multiple possible locations
        possible_paths = [
            kb_file_path,
            os.path.join(current_dir, "..", "knowledge_base", "docs", "kb_data.txt"),
            os.path.join(os.getcwd(), "knowledge_base", "docs", "kb_data.txt"),
            "knowledge_base/docs/kb_data.txt",
            "../knowledge_base/docs/kb_data.txt"
        ]
        
        results = {}
        for path in possible_paths:
            full_path = os.path.abspath(path)
            exists = os.path.exists(full_path)
            results[path] = {
                "full_path": full_path,
                "exists": exists,
                "writable": os.access(os.path.dirname(full_path), os.W_OK) if exists else False
            }
            if exists:
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    results[path]['line_count'] = len(content.splitlines())
                    results[path]['file_size'] = len(content)
                except Exception as e:
                    results[path]['read_error'] = str(e)
        
        return {
            "kb_service_file_path": kb_file_path,
            "current_working_dir": os.getcwd(),
            "script_dir": current_dir,
            "file_check_results": results
        }
    except Exception as e:
        return {"error": str(e)}

# Add to backend/api/admin.py
@router.get("/kb/current-file")
async def get_current_kb_file():
    """Get the current content of the KB file that the app is using"""
    try:
        file_path = kb_service.kb_file_path
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.splitlines()
        
        return {
            "file_path": file_path,
            "line_count": len(lines),
            "file_size": len(content),
            "content": content,
            "last_10_lines": lines[-10:] if len(lines) > 10 else lines
        }
    except Exception as e:
        return {"error": str(e)}
@router.get("/kb/force-update-file-get")
async def force_update_kb_file_get():
    """GET endpoint to force update kb_data.txt file (for testing)"""
    return await force_update_kb_file()  
 
# Add to backend/api/admin.py
@router.post("/kb/force-update-file")
async def force_update_kb_file():
    """Force update kb_data.txt file with ALL ChromaDB entries"""
    try:
        # Get all ChromaDB entries
        chroma_entries = chroma_client.get_all_entries()
        
        # Create header
        file_content = "# Knowledge Base Entries\n"
        file_content += f"# Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        file_content += f"# Total Entries: {len(chroma_entries)}\n\n"
        
        for entry in chroma_entries:
            metadata = entry.get('metadata', {})
            kb_id = entry.get('id', '')
            
            # Extract KB number
            if kb_id.startswith('KB_'):
                kb_number = kb_id.split('_')[1]
            else:
                kb_number = kb_id[2:] if kb_id.startswith('KB') else kb_id
            
            file_content += f"\n{'='*50}\n"
            file_content += f"[KB_ID: {kb_number}]\n\n"
            file_content += f"Use Case: {metadata.get('use_case', 'Unknown')}\n\n"
            
            required_info = metadata.get('required_info', '')
            if required_info:
                file_content += "Required Info:\n"
                for info in required_info.split(','):
                    file_content += f"- {info.strip()}\n"
                file_content += "\n"
            
            solution_steps = metadata.get('solution_steps', '')
            if solution_steps:
                file_content += "Solution Steps:\n"
                # Format solution steps properly
                if '\n' in solution_steps:
                    file_content += f"{solution_steps}\n"
                else:
                    file_content += f"- {solution_steps}\n"
            
            file_content += f"{'-'*50}\n"
        
        # Write to file
        kb_file_path = kb_service.kb_file_path
        os.makedirs(os.path.dirname(kb_file_path), exist_ok=True)
        
        with open(kb_file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        # Verify the write
        with open(kb_file_path, 'r', encoding='utf-8') as f:
            written_content = f.read()
        
        return {
            "message": "KB file force updated successfully",
            "file_path": kb_file_path,
            "entries_processed": len(chroma_entries),
            "file_size": len(written_content),
            "line_count": len(written_content.splitlines()),
            "file_exists": os.path.exists(kb_file_path)
        }
        
    except Exception as e:
        logger.error(f"Error force updating KB file: {e}")
        return {"error": str(e)}
    

# Add to backend/api/admin.py
@router.get("/kb/file-monitor")
async def monitor_kb_file():
    """Monitor KB file for changes"""
    try:
        file_path = kb_service.kb_file_path
        
        if not os.path.exists(file_path):
            return {"error": "File does not exist"}
        
        stat = os.stat(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.splitlines()
        
        return {
            "file_path": file_path,
            "last_modified": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            "file_size": stat.st_size,
            "line_count": len(lines),
            "first_5_lines": lines[:5],
            "last_5_lines": lines[-5:],
            "file_hash": hash(content)  # Changes if content changes
        }
    except Exception as e:
        return {"error": str(e)}
    
# Add to backend/api/admin.py
@router.get("/debug/kb-append-status")
async def debug_kb_append_status():
    """Check if append_to_kb_file is being called"""
    try:
        # Test the append method directly
        test_result = kb_service.append_to_kb_file(
            "TEST_001", 
            "Test Use Case", 
            ["Test Info 1", "Test Info 2"], 
            ["Step 1: Test", "Step 2: Test"]
        )
        
        # Check file after test
        with open(kb_service.kb_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "append_test_result": test_result,
            "file_after_test_size": len(content),
            "file_after_test_lines": len(content.splitlines()),
            "last_5_lines": content.splitlines()[-5:] if content.splitlines() else []
        }
    except Exception as e:
        return {"error": str(e)}
    
@router.delete("/chroma/entries/{kb_id}")
async def delete_chroma_entry(kb_id: str):
    """Delete a KB entry from ChromaDB"""
    try:
        success = chroma_client.delete_entry(kb_id)
        if success:
            return {"message": f"KB entry {kb_id} deleted successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to delete KB entry")
    except Exception as e:
        logger.error(f"Error deleting ChromaDB entry: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")