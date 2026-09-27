"""Intent normalization layer for HR Copilot.

This module provides deterministic mapping between LLM outputs and backend tools,
ensuring the LLM cannot arbitrarily select backend sources or tools.
"""

from typing import Dict, Any
from .pipeline import CopilotError


class IntentNormalizer:
    """Normalizes LLM intent output to backend-compatible format."""
    
    def __init__(self):
        # Deterministic intent → source mapping
        self.intent_source_mapping = {
            # Attendance operations
            'attendance_lookup': 'attendance',
            'attendance_update': 'attendance', 
            'attendance_create': 'attendance',
            'attendance_summary': 'attendance',
            'attendance_count': 'attendance',
            'attendance_trend': 'attendance',
            
            # Employee operations  
            'employee_lookup': 'employee',
            'employee_summary': 'employee',
            'employee_count': 'employee',
            
            # Leave operations
            'leave_lookup': 'leave',
            'leave_create': 'leave',
            'leave_update': 'leave', 
            'leave_cancel': 'leave',
            'leave_approve': 'leave',
            'leave_deny': 'leave',
            'leave_summary': 'leave',
            'leave_count': 'leave',
            'leave_trend': 'leave',
            
            # Absence operations (uses employee source for queries)
            'absence_lookup': 'employee',
            'absence_count': 'employee',
            
            # Comparison operations
            'comparison': 'employee',
        }
        
        # Intent → backend tool mapping
        self.intent_tool_mapping = {
            # Read operations
            'attendance_lookup': 'attendance_read_tool',
            'attendance_summary': 'attendance_read_tool', 
            'attendance_count': 'attendance_read_tool',
            'attendance_trend': 'attendance_read_tool',
            
            'employee_lookup': 'employee_lookup_tool',
            'employee_summary': 'employee_lookup_tool',
            'employee_count': 'employee_lookup_tool',
            
            'leave_lookup': 'leave_read_tool',
            'leave_summary': 'leave_read_tool',
            'leave_count': 'leave_read_tool',
            'leave_trend': 'leave_read_tool',
            
            'absence_lookup': 'absence_lookup_tool',
            'absence_count': 'absence_lookup_tool',
            
            'comparison': 'comparison_tool',
            
            # Write operations
            'attendance_update': 'attendance_update_tool',
            'attendance_create': 'attendance_create_tool',
            
            'leave_create': 'leave_create_tool',
            'leave_update': 'leave_update_tool',
            'leave_cancel': 'leave_cancel_tool',
            'leave_approve': 'leave_approve_tool',
            'leave_deny': 'leave_deny_tool',
        }
        
        # Read vs Write classification
        self.read_intents = {
            'attendance_lookup', 'attendance_summary', 'attendance_count', 'attendance_trend',
            'employee_lookup', 'employee_summary', 'employee_count', 
            'leave_lookup', 'leave_summary', 'leave_count', 'leave_trend',
            'absence_lookup', 'absence_count',
            'comparison', 'unknown'
        }
        
        self.write_intents = {
            'attendance_update', 'attendance_create', 'attendance_delete',
            'leave_create', 'leave_update', 'leave_cancel', 'leave_approve', 'leave_deny',
            'employee_update', 'bulk_attendance_update'
        }
        
        # Status normalization mapping
        self.status_mapping = {
            'absent': 'LEAVE',
            'present': 'PRESENT',
            'incomplete': 'INCOMPLETE', 
            'leave': 'LEAVE',
            'checked_in': 'INCOMPLETE',
            'completed': 'PRESENT'
        }
    
    def normalize_intent(self, llm_output: Dict[str, Any], original_query: str = "") -> Dict[str, Any]:
        """
        Normalize LLM output to backend-compatible intent format.
        
        Args:
            llm_output: Raw output from LLM
            original_query: Original user query for fallback processing
            
        Returns:
            Normalized intent with correct source and action_type
        """
        if not isinstance(llm_output, dict):
            raise CopilotError("invalid_intent", "LLM returned invalid intent format")
        
        intent_name = llm_output.get('intent')
        if not intent_name:
            raise CopilotError("invalid_intent", "Missing intent in LLM output")
        
        # Normalize the intent structure
        normalized = {
            'intent': intent_name,
            'entities': llm_output.get('entities', {}),
            'missing_information': llm_output.get('missing_information', []),
            'ambiguities': llm_output.get('ambiguities', []),
            'confidence': llm_output.get('confidence', 1.0),
            'original_query': original_query
        }
        
        # Deterministically set source based on intent, ignoring LLM's source
        if intent_name in self.intent_source_mapping:
            normalized['source'] = self.intent_source_mapping[intent_name]
        else:
            # Fallback for unknown intents
            normalized['source'] = None
            normalized['intent'] = 'unknown'
        
        # Deterministically set action_type
        if intent_name in self.write_intents:
            normalized['action_type'] = 'write'
            normalized['requires_approval'] = True
        else:
            normalized['action_type'] = 'read'
            normalized['requires_approval'] = False
        
        # Set backend tool
        if intent_name in self.intent_tool_mapping:
            normalized['backend_tool'] = self.intent_tool_mapping[intent_name]
        else:
            normalized['backend_tool'] = None
        
        # Normalize entities
        normalized['entities'] = self._normalize_entities(
            normalized['entities'], 
            intent_name, 
            original_query
        )
        
        return normalized
    
    def _normalize_entities(self, entities: Dict[str, Any], intent: str, query: str) -> Dict[str, Any]:
        """Normalize and validate entities."""
        if not isinstance(entities, dict):
            entities = {}
        
        normalized = entities.copy()
        
        # Normalize attendance status for write operations
        if intent in self.write_intents:
            # Try to extract status from various fields
            target_status = (
                entities.get('target_status') or 
                entities.get('attendance_status') or
                entities.get('status')
            )
            
            # Fallback: extract from query text
            if not target_status and query:
                query_lower = query.lower()
                for word, status in self.status_mapping.items():
                    if word in query_lower:
                        target_status = status
                        break
            
            if target_status:
                # Normalize status
                if target_status.lower() in self.status_mapping:
                    normalized['target_status'] = self.status_mapping[target_status.lower()]
                else:
                    normalized['target_status'] = target_status.upper()
        
        # Normalize employee name
        if entities.get('employee_name'):
            # Clean up employee name
            name = str(entities['employee_name']).strip()
            if name:
                normalized['employee_name'] = name
        
        # Normalize temporal expressions to date ranges if possible
        temporal_expr = entities.get('temporal_expression')
        if temporal_expr and not entities.get('date_range'):
            # This will be handled by the existing temporal resolution logic
            normalized['temporal_expression'] = temporal_expr
        
        # Clean up empty values
        normalized = {k: v for k, v in normalized.items() if v is not None and v != ""}
        
        return normalized
    
    def validate_normalized_intent(self, normalized_intent: Dict[str, Any]) -> bool:
        """Validate that the normalized intent is properly formed."""
        required_fields = ['intent', 'source', 'action_type', 'entities']
        
        for field in required_fields:
            if field not in normalized_intent:
                raise CopilotError("invalid_intent", f"Missing required field: {field}")
        
        intent_name = normalized_intent['intent']
        source = normalized_intent['source']
        
        # Validate intent-source consistency
        expected_source = self.intent_source_mapping.get(intent_name)
        if expected_source and source != expected_source:
            raise CopilotError(
                "intent_source_mismatch", 
                f"Intent '{intent_name}' expects source '{expected_source}' but got '{source}'"
            )
        
        return True


# Create singleton instance
intent_normalizer = IntentNormalizer()