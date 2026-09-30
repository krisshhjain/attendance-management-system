"""Bounded session memory for HR Copilot to reduce LLM context size."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from django.core.cache import cache
from django.utils import timezone


@dataclass
class SessionState:
    """Compact session state for conversation continuity."""
    last_intent: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    current_date: Optional[str] = None
    current_date_end: Optional[str] = None
    current_section: Optional[str] = None
    current_subsection: Optional[str] = None
    current_department: Optional[str] = None
    pending_action: Optional[str] = None
    current_request_id: Optional[int] = None
    current_request_type: Optional[str] = None
    current_metric: Optional[str] = None
    last_query: Optional[str] = None
    context_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


class SessionMemoryManager:
    """Manages bounded session memory to reduce LLM context."""
    
    MAX_CONTEXT_ENTRIES = 3  # Keep only last 3 interactions
    CACHE_TIMEOUT = 3600  # 1 hour
    
    def __init__(self):
        self.cache_prefix = "hr_copilot_session:"
    
    def get_session_state(self, session_id: str) -> SessionState:
        """Get current session state."""
        cache_key = f"{self.cache_prefix}{session_id}"
        data = cache.get(cache_key, {})
        return SessionState.from_dict(data)
    
    def update_session_state(self, session_id: str, **updates) -> SessionState:
        """Update session state with new information."""
        state = self.get_session_state(session_id)
        
        # Update with new values
        for key, value in updates.items():
            if hasattr(state, key) and value is not None:
                setattr(state, key, value)
        
        state.context_count += 1
        
        # Cache the updated state
        cache_key = f"{self.cache_prefix}{session_id}"
        cache.set(cache_key, state.to_dict(), self.CACHE_TIMEOUT)
        
        return state
    
    def get_compact_context(self, session_id: str) -> Dict[str, Any]:
        """Get compact context for LLM calls."""
        state = self.get_session_state(session_id)
        context = state.to_dict()
        
        # Remove internal tracking fields
        context.pop('context_count', None)
        # The previous question is useful for diagnostics but wastes scarce
        # prompt tokens and can make a follow-up depend on stale wording.
        context.pop('last_query', None)
        
        # Keep only relevant context
        if not context.get('employee_id') and not context.get('employee_name'):
            context.pop('employee_id', None)
            context.pop('employee_name', None)
        
        return context
    
    def clear_session(self, session_id: str):
        """Clear session memory."""
        cache_key = f"{self.cache_prefix}{session_id}"
        cache.delete(cache_key)
    
    def extract_context_from_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant context from an intent for future use."""
        context = {}
        entities = intent.get("entities", {})
        
        if intent.get("intent"):
            context["last_intent"] = intent["intent"]
        
        if entities.get("employee_id"):
            context["employee_id"] = entities["employee_id"]
            try:
                from employees.models import Employee
                employee = Employee.objects.select_related("user").filter(pk=entities["employee_id"]).first()
                if employee:
                    context["employee_name"] = employee.user.get_full_name().strip() or employee.user.email
                    context["employee_email"] = employee.user.email
            except Exception:
                pass
        
        if entities.get("employee_name"):
            context["employee_name"] = entities["employee_name"]
        
        if entities.get("date_range"):
            context["current_date"] = entities["date_range"].get("start")
            context["current_date_end"] = entities["date_range"].get("end")

        if entities.get("request_id"):
            context["current_request_id"] = entities["request_id"]
        if entities.get("intelligence_metric"):
            context["current_metric"] = entities["intelligence_metric"]
        elif entities.get("attendance_metric"):
            context["current_metric"] = entities["attendance_metric"]
        
        if entities.get("section"):
            context["current_section"] = entities["section"]

        if entities.get("subsection"):
            context["current_subsection"] = entities["subsection"]
        
        if entities.get("department"):
            context["current_department"] = entities["department"]
        
        if intent.get("action_type") == "write":
            context["pending_action"] = intent.get("intent")
        
        return context


# Singleton instance
session_memory = SessionMemoryManager()
