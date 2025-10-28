# backend/models/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo

# Add this function at the top of your files
def get_ist_time():
    """Get current time in India Standard Time (IST)"""
    # ist = pytz.timezone('Asia/Kolkata')
    # return datetime.now(ist)
    return datetime.now(ZoneInfo('Asia/Kolkata'))

class UserQuery(BaseModel):
    user_input: str
    session_id: Optional[str] = None


class IncidentResponse(BaseModel):
    message: str
    incident_id: Optional[str] = None
    session_id: str
    status: Optional[str] = None
    follow_up_question: Optional[str] = None
    action: Optional[str] = None
    show_action_buttons: Optional[bool] = False
    action_buttons: Optional[List[Dict[str, str]]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Hello! How can I help you?",
                "session_id": "abc123",
                "show_action_buttons": True,
                "action_buttons": [
                    {"label": "Track Incident", "value": "track"},
                    {"label": "Create New", "value": "create"}
                ]
            }
        }

class IncidentCreate(BaseModel):
    incident_id: str
    user_demand: str
    session_id: str
    status: str = "pending_info"
    kb_id: Optional[str] = None
    collected_info: Dict[str, Any] = Field(default_factory=dict)
    required_info: List[str] = Field(default_factory=list)
    missing_info: List[str] = Field(default_factory=list)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    is_new_kb_entry: bool = False
    needs_kb_approval: bool = False
    admin_message: Optional[str] = None  # Add this field
    created_on: datetime = Field(default_factory=get_ist_time)
    updated_on: datetime = Field(default_factory=get_ist_time)


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    collected_info: Optional[Dict[str, Any]] = None
    missing_info: Optional[List[str]] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    solution_steps: Optional[str] = None
    admin_message: Optional[str] = None  # Add this field
    updated_on: datetime = Field(default_factory=datetime.utcnow)


class StatusUpdateRequest(BaseModel):
    incident_id: str
    status: str


class KBEntry(BaseModel):
    kb_id: str
    use_case: str
    required_info: List[str]
    solution_steps: str
    questions: List[str] = Field(default_factory=list)
    created_on: datetime = Field(default_factory=datetime.utcnow)


class KBApprovalRequest(BaseModel):
    incident_id: str
    solution_steps: str


class AdminIncidentFilter(BaseModel):
    status: Optional[str] = None
    incident_id: Optional[str] = None
    needs_kb_approval: Optional[bool] = None


class SessionData(BaseModel):
    session_id: str
    active_incidents: List[str] = Field(default_factory=list)
    conversation_context: List[Dict[str, str]] = Field(default_factory=list)
    created_on: datetime = Field(default_factory=get_ist_time)
    updated_on: datetime = Field(default_factory=get_ist_time)
    