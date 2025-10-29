# backend/api/admin.py - FIXED VERSION
from fastapi import APIRouter, HTTPException, Query
from services.incident_service import incident_service
from services.kb_service import kb_service
from db.chroma import chroma_client
from db.mongo import mongo_client
from models.schemas import KBApprovalRequest
from typing import Optional, List, Dict, Any
import logging
import os
from datetime import datetime
import json

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


@router.put("/incidents/{incident_id}/admin-message")
async def update_admin_message(incident_id: str, request: Dict[str, str]):
    """Update admin message for an incident - allows custom messages for all statuses"""
    try:
        admin_message = request.get('admin_message', '').strip()
        
        # Get current incident to check status
        incident = mongo_client.get_incident_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # If message is empty, set appropriate default based on status
        if not admin_message:
            default_messages = {
                'pending_info': 'Still need some information.',
                'open': 'All information collected. Our team will contact you soon.',
                'resolved': 'Incident has been resolved successfully.',
                'closed': 'Incident has been closed.'
            }
            admin_message = default_messages.get(incident.get('status', ''), '')
        
        success = mongo_client.update_incident(incident_id, {
            'admin_message': admin_message,
            'updated_on': datetime.utcnow()
        })
        
        if success:
            return {
                "message": "Admin message updated successfully",
                "incident_id": incident_id,
                "admin_message": admin_message,
                "status": incident.get('status')
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to update admin message")
    except Exception as e:
        logger.error(f"Error updating admin message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
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
    """Delete a KB entry from ChromaDB and synchronize with text file"""
    try:
        # 1. First delete from ChromaDB
        success = chroma_client.delete_entry(kb_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to delete KB entry from ChromaDB")
        
        # 2. Synchronize with kb_data.txt file
        sync_result = await sync_kb_file_with_chroma()
        
        return {
            "message": f"KB entry {kb_id} deleted successfully and file synchronized",
            "sync_result": sync_result
        }
        
    except Exception as e:
        logger.error(f"Error deleting ChromaDB entry: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def sync_kb_file_with_chroma():
    """Sync the kb_data.txt file with current ChromaDB state"""
    try:
        # Get all entries from ChromaDB
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
            "message": "KB file synchronized successfully",
            "file_path": kb_file_path,
            "entries_count": len(chroma_entries),
            "file_size": len(written_content),
            "line_count": len(written_content.splitlines())
        }
        
    except Exception as e:
        logger.error(f"Error syncing KB file: {e}")
        return {"error": str(e)}


@router.get("/kb/force-sync")
async def force_sync_kb():
    """Force synchronization between ChromaDB and kb_data.txt"""
    try:
        result = await sync_kb_file_with_chroma()
        return result
    except Exception as e:
        logger.error(f"Error forcing KB sync: {e}")
        return {"error": str(e)}


@router.get("/debug/kb-sync-status")
async def debug_kb_sync_status():
    """Debug endpoint to check sync status between ChromaDB and file"""
    try:
        # Check ChromaDB
        chroma_entries = chroma_client.get_all_entries()
        chroma_count = len(chroma_entries)
        
        # Check file
        kb_file_path = kb_service.kb_file_path
        file_exists = os.path.exists(kb_file_path)
        file_count = 0
        
        if file_exists:
            with open(kb_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                file_count = content.count("KB_ID:")
        
        # Get ChromaDB IDs for comparison
        chroma_ids = [entry.get('id', '') for entry in chroma_entries]
        
        # Get file IDs for comparison
        file_ids = []
        if file_exists:
            with open(kb_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    if line.strip().startswith('[KB_ID:'):
                        # Extract KB ID from format like [KB_ID: 001]
                        kb_id_part = line.strip()[7:-1]  # Remove '[KB_ID:' and ']'
                        file_ids.append(f"KB_{kb_id_part.strip()}")
        
        # Check if IDs match
        ids_match = set(chroma_ids) == set(file_ids)
        
        return {
            "chroma_db_entries": chroma_count,
            "file_entries": file_count,
            "in_sync": chroma_count == file_count and ids_match,
            "file_exists": file_exists,
            "file_size": os.path.getsize(kb_file_path) if file_exists else 0,
            "chroma_ids": chroma_ids,
            "file_ids": file_ids,
            "ids_match": ids_match,
            "missing_in_file": list(set(chroma_ids) - set(file_ids)),
            "missing_in_chroma": list(set(file_ids) - set(chroma_ids))
        }
        
    except Exception as e:
        logger.error(f"Error checking sync status: {e}")
        return {"error": str(e)}


@router.post("/kb/add-entry")
async def add_kb_entry(entry_data: Dict[str, Any]):
    """Add a new KB entry to both ChromaDB and text file"""
    try:
        kb_id = entry_data.get('kb_id')
        use_case = entry_data.get('use_case')
        required_info = entry_data.get('required_info', '')
        solution_steps = entry_data.get('solution_steps', '')
        questions = entry_data.get('questions', '')
        
        if not kb_id or not use_case:
            raise HTTPException(status_code=400, detail="KB ID and use case are required")
        
        # Add to ChromaDB
        chroma_success = chroma_client.add_entry(
            kb_id=kb_id,
            use_case=use_case,
            required_info=required_info,
            solution_steps=solution_steps,
            questions=questions
        )
        
        if not chroma_success:
            raise HTTPException(status_code=400, detail="Failed to add entry to ChromaDB")
        
        # Synchronize with text file
        sync_result = await sync_kb_file_with_chroma()
        
        return {
            "message": "KB entry added successfully and file synchronized",
            "kb_id": kb_id,
            "sync_result": sync_result
        }
        
    except Exception as e:
        logger.error(f"Error adding KB entry: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    # Add these debugging endpoints to api/admin.py (at the end before last line)

@router.get("/debug/system-status")
async def debug_system_status():
    """Comprehensive system status check"""
    try:
        from services.embedding_wrapper import embedding_service
        
        # Test MongoDB
        mongo_status = "OK" if mongo_client.client else "NOT CONNECTED"
        
        # Test ChromaDB
        try:
            chroma_entries = chroma_client.get_all_entries()
            chroma_status = f"OK - {len(chroma_entries)} entries"
        except Exception as e:
            chroma_status = f"ERROR: {str(e)}"
        
        # Test embedding service
        try:
            test_emb = embedding_service.generate_embedding("test")
            embedding_status = f"OK - dim: {len(test_emb)}" if test_emb else "FAILED"
        except Exception as e:
            embedding_status = f"ERROR: {str(e)}"
        
        # Test LLM service
        try:
            from services.llm_service import llm_service
            test_response = llm_service.generate_response("Say 'test'", temperature=0.1)
            llm_status = "OK" if test_response else "FAILED"
        except Exception as e:
            llm_status = f"ERROR: {str(e)}"
        
        # Check KB file
        kb_file_status = "EXISTS" if os.path.exists(kb_service.kb_file_path) else "NOT FOUND"
        
        return {
            "mongodb": mongo_status,
            "chromadb": chroma_status,
            "embedding_service": embedding_status,
            "llm_service": llm_status,
            "kb_file": kb_file_status,
            "kb_file_path": kb_service.kb_file_path,
            "environment": settings.ENVIRONMENT
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/debug/test-kb-search")
async def debug_test_kb_search(query: str = "outlook not opening"):
    """Test KB search functionality"""
    try:
        logger.info(f"Testing KB search with query: {query}")
        result = kb_service.search_kb(query)
        
        return {
            "query": query,
            "best_match_found": result['best_match'] is not None,
            "best_match": result['best_match'],
            "highest_similarity": result.get('highest_enhanced_similarity', 0),
            "total_matches": len(result.get('matches', [])),
            "all_matches": result.get('matches', [])
        }
    except Exception as e:
        logger.error(f"Error testing KB search: {e}")
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@router.get("/debug/test-intent-detection")
async def debug_test_intent_detection(query: str = "hello"):
    """Test intent detection"""
    try:
        from services.llm_service import llm_service
        
        intent = llm_service.detect_intent(
            user_input=query,
            conversation_history=[],
            has_active_incident=False,
            session_id="test-session"
        )
        
        return {
            "query": query,
            "detected_intent": intent,
            "is_valid": intent is not None and 'intent' in intent
        }
    except Exception as e:
        logger.error(f"Error testing intent detection: {e}")
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}
