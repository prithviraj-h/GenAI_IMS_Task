#backend/db/mongo.py
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure
from core.config import settings
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MongoDBClient:
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db = None
        self.incidents_collection = None
        self.sessions_collection = None
        
    def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = MongoClient(settings.MONGO_URI)
            self.client.admin.command('ping')
            self.db = self.client[settings.MONGO_DB]
            self.incidents_collection = self.db[settings.INCIDENT_COLLECTION]
            self.sessions_collection = self.db[settings.SESSION_COLLECTION]
            
            # Create indexes
            self.incidents_collection.create_index([("incident_id", ASCENDING)], unique=True)
            self.incidents_collection.create_index([("status", ASCENDING)])
            self.incidents_collection.create_index([("session_id", ASCENDING)])
            self.sessions_collection.create_index([("session_id", ASCENDING)], unique=True)
            
            logger.info("Connected to MongoDB successfully")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    # Incident Operations
    def create_incident(self, incident_data: Dict[str, Any]) -> bool:
        """Create a new incident"""
        try:
            self.incidents_collection.insert_one(incident_data)
            return True
        except Exception as e:
            logger.error(f"Error creating incident: {e}")
            return False
    
    def get_incident_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Get incident by ID"""
        try:
            incident = self.incidents_collection.find_one({"incident_id": incident_id})
            if incident and '_id' in incident:
                incident['_id'] = str(incident['_id'])
            return incident
        except Exception as e:
            logger.error(f"Error getting incident: {e}")
            return None
    
    def update_incident(self, incident_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an incident"""
        try:
            update_data['updated_on'] = datetime.utcnow()
            result = self.incidents_collection.update_one(
                {"incident_id": incident_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating incident: {e}")
            return False
    
    def get_incidents_by_filter(self, filter_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get incidents by filter"""
        try:
            incidents = list(self.incidents_collection.find(filter_dict))
            for incident in incidents:
                if '_id' in incident:
                    incident['_id'] = str(incident['_id'])
            return incidents
        except Exception as e:
            logger.error(f"Error getting incidents: {e}")
            return []
    
    def get_all_incidents(self) -> List[Dict[str, Any]]:
        """Get all incidents sorted by creation date (newest first)"""
        try:
            incidents = list(self.incidents_collection.find({}).sort("created_on", -1))
            for incident in incidents:
                if '_id' in incident:
                    incident['_id'] = str(incident['_id'])
            return incidents
        except Exception as e:
            logger.error(f"Error getting all incidents: {e}")
            return []
    
    def get_incidents_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get incidents by status sorted by creation date (newest first)"""
        try:
            incidents = list(self.incidents_collection.find({"status": status}).sort("created_on", -1))
            for incident in incidents:
                if '_id' in incident:
                    incident['_id'] = str(incident['_id'])
            return incidents
        except Exception as e:
            logger.error(f"Error getting incidents by status: {e}")
            return []
    
    def get_incidents_by_filter(self, filter_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get incidents by filter sorted by creation date (newest first)"""
        try:
            incidents = list(self.incidents_collection.find(filter_dict).sort("created_on", -1))
            for incident in incidents:
                if '_id' in incident:
                    incident['_id'] = str(incident['_id'])
            return incidents
        except Exception as e:
            logger.error(f"Error getting incidents: {e}")
            return []
    
    def get_incidents_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get incidents by session ID"""
        try:
            incidents = list(self.incidents_collection.find({"session_id": session_id}))
            for incident in incidents:
                if '_id' in incident:
                    incident['_id'] = str(incident['_id'])
            return incidents
        except Exception as e:
            logger.error(f"Error getting incidents by session: {e}")
            return []
    
    # Session Operations
    def create_session(self, session_data: Dict[str, Any]) -> bool:
        """Create a new session"""
        try:
            self.sessions_collection.insert_one(session_data)
            return True
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        try:
            session = self.sessions_collection.find_one({"session_id": session_id})
            if session and '_id' in session:
                session['_id'] = str(session['_id'])
            return session
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def update_session(self, session_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a session"""
        try:
            update_data['updated_on'] = datetime.utcnow()
            result = self.sessions_collection.update_one(
                {"session_id": session_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False


# Global MongoDB client instance
mongo_client = MongoDBClient()