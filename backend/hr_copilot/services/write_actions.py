"""Write action planning and approval workflow for HR Copilot."""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import uuid

from django.utils import timezone
from django.db import transaction

from .pipeline import CopilotError, derive_scope
from .employee_resolver import employee_resolver
from employees.models import Employee
from attendance.models import Attendance
from leave_management.models import LeaveRequest, LeaveType


class WriteActionPlanner:
    """Plans and validates write actions for HR Copilot."""
    
    def __init__(self):
        self.write_intents = {
            'attendance_update', 'attendance_create', 'leave_create', 
            'leave_cancel', 'leave_approve', 'leave_deny', 'bulk_attendance_update'
        }
    
    def is_write_action(self, intent: Dict[str, Any]) -> bool:
        """Check if the intent represents a write action."""
        return (intent.get('intent', '') in self.write_intents or 
                intent.get('action_type') == 'write' or
                intent.get('requires_approval', False))
    
    def plan_write_action(self, intent: Dict[str, Any], user, session_id: str) -> Dict[str, Any]:
        """Plan a write action and create a pending action for approval."""
        
        # Validate this is actually a write action
        if not self.is_write_action(intent):
            raise CopilotError("invalid_action", "This is not a write action")
        
        # Derive user scope for authorization
        scope = derive_scope(user)
        
        # Plan the specific action based on intent
        if intent['intent'] == 'attendance_update':
            return self._plan_attendance_update(intent, user, scope, session_id)
        elif intent['intent'] == 'attendance_create':
            return self._plan_attendance_create(intent, user, scope, session_id)
        elif intent['intent'] == 'leave_create':
            return self._plan_leave_create(intent, user, scope, session_id)
        elif intent['intent'] == 'leave_cancel':
            return self._plan_leave_cancel(intent, user, scope, session_id)
        else:
            raise CopilotError("unsupported_write", f"Write action '{intent['intent']}' not yet implemented")
    
    def _plan_attendance_update(self, intent: Dict[str, Any], user, scope: Dict, session_id: str) -> Dict[str, Any]:
        """Plan an attendance update action."""
        entities = intent.get('entities', {})
        
        # Resolve employee
        employee_resolution = self._resolve_target_employee(entities, user, scope)
        
        # Resolve target date
        target_date = self._resolve_target_date(entities)
        
        # Resolve target status with fallback logic
        target_status = entities.get('target_status', entities.get('attendance_status'))
        
        # Fallback: try to infer from query text if not explicitly provided
        if not target_status:
            # Get the original query text if available
            query_text = intent.get('original_query', '').lower()
            if 'absent' in query_text or 'as absent' in query_text:
                target_status = 'LEAVE'
            elif 'present' in query_text or 'as present' in query_text:
                target_status = 'PRESENT'
            elif 'incomplete' in query_text or 'as incomplete' in query_text:
                target_status = 'INCOMPLETE'
            elif 'leave' in query_text or 'on leave' in query_text:
                target_status = 'LEAVE'
        
        if not target_status:
            raise CopilotError("missing_status", "Target attendance status is required. Please specify 'present', 'absent', or 'incomplete'.")
        
        # Normalize status values
        status_mapping = {
            'absent': 'LEAVE',
            'present': 'PRESENT', 
            'incomplete': 'INCOMPLETE',
            'leave': 'LEAVE'
        }
        
        if target_status.lower() in status_mapping:
            target_status = status_mapping[target_status.lower()]
        else:
            target_status = target_status.upper()
        
        # Validate target status
        valid_statuses = ['PRESENT', 'INCOMPLETE', 'LEAVE']
        if target_status not in valid_statuses:
            raise CopilotError("invalid_status", f"Status must be one of: {', '.join(valid_statuses)}")
        
        # Get current state
        current_attendance = Attendance.objects.filter(
            employee_id=employee_resolution['employee_id'],
            date=target_date
        ).first()
        
        current_state = {
            'exists': current_attendance is not None,
            'current_status': current_attendance.status if current_attendance else None,
            'employee_id': employee_resolution['employee_id'],
            'date': target_date.isoformat()
        }
        
        # Create pending action
        pending_action = {
            'action_id': str(uuid.uuid4()),
            'session_id': session_id,
            'user_id': user.id,
            'action_type': 'attendance_update',
            'intent': intent['intent'],
            'source': intent['source'],
            'target_data': {
                'employee_id': employee_resolution['employee_id'],
                'employee_name': employee_resolution['employee_name'],
                'date': target_date.isoformat(),
                'target_status': target_status
            },
            'proposed_changes': {
                'status': target_status,
                'operation': 'update' if current_attendance else 'create'
            },
            'current_state': current_state,
            'validated': True,
            'authorization_scope': scope,
            'requires_confirmation': True,
            'description': f"Change {employee_resolution['employee_name']}'s attendance on {target_date.strftime('%B %d, %Y')} to {target_status}",
            'expires_at': timezone.now() + timedelta(minutes=10)
        }
        
        # Add warning if this changes existing data
        if current_attendance and current_attendance.status != target_status:
            pending_action['warning_message'] = f"This will change existing status from {current_attendance.status} to {target_status}"
        
        return pending_action
    
    def _plan_attendance_create(self, intent: Dict[str, Any], user, scope: Dict, session_id: str) -> Dict[str, Any]:
        """Plan an attendance creation action."""
        # Similar to update but ensures no existing record
        entities = intent.get('entities', {})
        
        employee_resolution = self._resolve_target_employee(entities, user, scope)
        target_date = self._resolve_target_date(entities)
        target_status = entities.get('target_status', 'PRESENT').upper()
        
        # Check if attendance already exists
        existing = Attendance.objects.filter(
            employee_id=employee_resolution['employee_id'],
            date=target_date
        ).exists()
        
        if existing:
            raise CopilotError("attendance_exists", f"Attendance record already exists for {target_date}")
        
        pending_action = {
            'action_id': str(uuid.uuid4()),
            'session_id': session_id,
            'user_id': user.id,
            'action_type': 'attendance_create',
            'intent': intent['intent'],
            'source': intent['source'],
            'target_data': {
                'employee_id': employee_resolution['employee_id'],
                'employee_name': employee_resolution['employee_name'],
                'date': target_date.isoformat(),
                'target_status': target_status
            },
            'proposed_changes': {
                'status': target_status,
                'operation': 'create'
            },
            'current_state': {'exists': False},
            'validated': True,
            'authorization_scope': scope,
            'requires_confirmation': True,
            'description': f"Create attendance record for {employee_resolution['employee_name']} on {target_date.strftime('%B %d, %Y')} as {target_status}",
            'expires_at': timezone.now() + timedelta(minutes=10)
        }
        
        return pending_action
    
    def _plan_leave_create(self, intent: Dict[str, Any], user, scope: Dict, session_id: str) -> Dict[str, Any]:
        """Plan a leave request creation action."""
        entities = intent.get('entities', {})
        
        employee_resolution = self._resolve_target_employee(entities, user, scope)
        start_date = self._resolve_target_date(entities)
        
        # Default to single day leave if no duration specified
        duration_days = entities.get('duration_days', 1)
        end_date = start_date + timedelta(days=duration_days - 1)
        
        # Get default leave type
        leave_type = LeaveType.objects.first()  # Use first available leave type as default
        if not leave_type:
            raise CopilotError("no_leave_types", "No leave types are configured in the system")
        
        reason = entities.get('reason', 'Leave request created via HR Copilot')
        
        pending_action = {
            'action_id': str(uuid.uuid4()),
            'session_id': session_id,
            'user_id': user.id,
            'action_type': 'leave_create',
            'intent': intent['intent'],
            'source': intent['source'],
            'target_data': {
                'employee_id': employee_resolution['employee_id'],
                'employee_name': employee_resolution['employee_name'],
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'duration_days': duration_days,
                'leave_type_id': leave_type.id,
                'reason': reason
            },
            'proposed_changes': {
                'operation': 'create',
                'leave_type': leave_type.name,
                'duration': f"{duration_days} day{'s' if duration_days != 1 else ''}"
            },
            'current_state': {'exists': False},
            'validated': True,
            'authorization_scope': scope,
            'requires_confirmation': True,
            'description': f"Create {duration_days}-day leave request for {employee_resolution['employee_name']} starting {start_date.strftime('%B %d, %Y')}",
            'expires_at': timezone.now() + timedelta(minutes=10)
        }
        
        return pending_action
    
    def _plan_leave_cancel(self, intent: Dict[str, Any], user, scope: Dict, session_id: str) -> Dict[str, Any]:
        """Plan a leave cancellation action."""
        entities = intent.get('entities', {})
        
        # If no specific employee mentioned, assume user wants to cancel their own leave
        if not entities.get('employee_name') and not entities.get('employee_email'):
            employee_id = user.employee.id if hasattr(user, 'employee') else None
            if not employee_id:
                raise CopilotError("no_employee_profile", "Cannot find your employee profile")
            employee_name = f"{user.first_name} {user.last_name}"
        else:
            employee_resolution = self._resolve_target_employee(entities, user, scope)
            employee_id = employee_resolution['employee_id']
            employee_name = employee_resolution['employee_name']
        
        # Find recent pending/approved leave requests
        recent_leaves = LeaveRequest.objects.filter(
            employee_id=employee_id,
            status__in=['PENDING', 'APPROVED'],
            start_date__gte=timezone.now().date()
        ).order_by('-created_at')[:5]
        
        if not recent_leaves.exists():
            raise CopilotError("no_leave_requests", f"No pending or approved leave requests found for {employee_name}")
        
        # Use the most recent leave request
        leave_request = recent_leaves.first()
        
        pending_action = {
            'action_id': str(uuid.uuid4()),
            'session_id': session_id,
            'user_id': user.id,
            'action_type': 'leave_cancel',
            'intent': intent['intent'],
            'source': intent['source'],
            'target_data': {
                'employee_id': employee_id,
                'employee_name': employee_name,
                'leave_request_id': leave_request.id,
                'start_date': leave_request.start_date.isoformat(),
                'end_date': leave_request.end_date.isoformat()
            },
            'proposed_changes': {
                'operation': 'cancel',
                'new_status': 'CANCELLED'
            },
            'current_state': {
                'status': leave_request.status,
                'leave_type': leave_request.leave_type.name,
                'duration_days': leave_request.duration_days
            },
            'validated': True,
            'authorization_scope': scope,
            'requires_confirmation': True,
            'description': f"Cancel {employee_name}'s leave request from {leave_request.start_date.strftime('%B %d, %Y')} to {leave_request.end_date.strftime('%B %d, %Y')}",
            'warning_message': "This action cannot be undone. The leave request will be permanently cancelled.",
            'expires_at': timezone.now() + timedelta(minutes=10)
        }
        
        return pending_action
    
    def _resolve_target_employee(self, entities: Dict, user, scope: Dict) -> Dict[str, Any]:
        """Resolve the target employee for the action."""
        employee_name = entities.get('employee_name')
        employee_email = entities.get('employee_email')
        
        if not employee_name and not employee_email:
            # Default to current user if no employee specified
            if hasattr(user, 'employee'):
                return {
                    'employee_id': user.employee.id,
                    'employee_name': f"{user.first_name} {user.last_name}"
                }
            else:
                raise CopilotError("employee_required", "Employee name or email is required")
        
        # Resolve employee using existing resolver
        resolution = employee_resolver.resolve_employee(
            name=employee_name,
            email=employee_email
        )
        
        if resolution.status == 'not_found':
            raise CopilotError("employee_not_found", "Employee not found")
        elif resolution.status == 'ambiguous':
            raise CopilotError("employee_ambiguous", "Multiple employees match. Please provide email address.")
        
        # Verify employee is within scope
        employee = Employee.objects.get(id=resolution.employee_id)
        if not scope['unrestricted']:
            if employee.section not in scope['sections']:
                raise CopilotError("scope_denied", "You don't have access to this employee", 403)
            if scope['subsections'] and employee.subsection not in scope['subsections']:
                raise CopilotError("scope_denied", "You don't have access to this employee", 403)
        
        return {
            'employee_id': resolution.employee_id,
            'employee_name': f"{employee.user.first_name} {employee.user.last_name}"
        }
    
    def _resolve_target_date(self, entities: Dict) -> datetime.date:
        """Resolve the target date for the action."""
        # Check if there's an explicit date range
        if entities.get('date_range'):
            date_str = entities['date_range']['start']
            return datetime.fromisoformat(date_str).date()
        
        # Check temporal expression
        temporal_expr = entities.get('temporal_expression', 'today').lower()
        
        today = timezone.now().date()
        
        if temporal_expr in ['today', 'now']:
            return today
        elif temporal_expr == 'yesterday':
            return today - timedelta(days=1)
        elif temporal_expr == 'tomorrow':
            return today + timedelta(days=1)
        elif temporal_expr == 'two days ago':
            return today - timedelta(days=2)
        else:
            # Default to today for unrecognized expressions
            return today


# Create singleton instance
write_action_planner = WriteActionPlanner()