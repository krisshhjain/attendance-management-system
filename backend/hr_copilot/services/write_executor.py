"""Write action executor with human-in-the-loop approval for HR Copilot."""

from django.db import transaction
from django.utils import timezone
from datetime import datetime
from typing import Dict, Any

from .pipeline import CopilotError
from employees.models import Employee
from attendance.models import Attendance
from leave_management.models import LeaveRequest


class WriteActionExecutor:
    """Executes approved write actions with transactional safety."""
    
    def execute_approved_action(self, pending_action: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute a validated and approved pending action."""
        
        # Validate action is executable
        if not pending_action.get('validated'):
            raise CopilotError("action_not_validated", "Action must be validated before execution")
        
        # Revalidate authorization at execution time
        self._revalidate_authorization(pending_action, user)
        
        action_type = pending_action['action_type']
        
        try:
            with transaction.atomic():
                if action_type == 'attendance_update':
                    return self._execute_attendance_update(pending_action)
                elif action_type == 'attendance_create':
                    return self._execute_attendance_create(pending_action)
                elif action_type == 'leave_create':
                    return self._execute_leave_create(pending_action)
                elif action_type == 'leave_cancel':
                    return self._execute_leave_cancel(pending_action)
                else:
                    raise CopilotError("unsupported_action", f"Action type '{action_type}' not implemented")
                    
        except Exception as e:
            # Log the error and re-raise
            raise CopilotError("execution_failed", f"Action execution failed: {str(e)}")
    
    def _execute_attendance_update(self, pending_action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute attendance update/create action."""
        target_data = pending_action['target_data']
        proposed_changes = pending_action['proposed_changes']
        
        employee_id = target_data['employee_id']
        target_date = datetime.fromisoformat(target_data['date']).date()
        target_status = proposed_changes['status']
        
        # Get or create attendance record
        attendance, created = Attendance.objects.get_or_create(
            employee_id=employee_id,
            date=target_date,
            defaults={
                'status': target_status,
                'check_in': None,
                'check_out': None,
                'working_duration': None
            }
        )
        
        if not created:
            # Update existing record
            old_status = attendance.status
            attendance.status = target_status
            attendance.save()
            
            result = {
                'success': True,
                'operation': 'updated',
                'employee_name': target_data['employee_name'],
                'date': target_date.isoformat(),
                'old_status': old_status,
                'new_status': target_status,
                'message': f"Updated {target_data['employee_name']}'s attendance on {target_date.strftime('%B %d, %Y')} from {old_status} to {target_status}"
            }
        else:
            result = {
                'success': True,
                'operation': 'created',
                'employee_name': target_data['employee_name'],
                'date': target_date.isoformat(),
                'status': target_status,
                'message': f"Created attendance record for {target_data['employee_name']} on {target_date.strftime('%B %d, %Y')} as {target_status}"
            }
        
        return result
    
    def _execute_attendance_create(self, pending_action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute attendance creation action."""
        # Same as update but ensures creation
        return self._execute_attendance_update(pending_action)
    
    def _execute_leave_create(self, pending_action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute leave request creation action."""
        target_data = pending_action['target_data']
        
        employee_id = target_data['employee_id']
        start_date = datetime.fromisoformat(target_data['start_date']).date()
        end_date = datetime.fromisoformat(target_data['end_date']).date()
        duration_days = target_data['duration_days']
        leave_type_id = target_data['leave_type_id']
        reason = target_data['reason']
        
        # Create leave request
        leave_request = LeaveRequest.objects.create(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            reason=reason,
            status='PENDING'  # Default to pending for approval workflow
        )
        
        result = {
            'success': True,
            'operation': 'created',
            'employee_name': target_data['employee_name'],
            'leave_request_id': leave_request.id,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'duration_days': duration_days,
            'status': 'PENDING',
            'message': f"Created {duration_days}-day leave request for {target_data['employee_name']} from {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}"
        }
        
        return result
    
    def _execute_leave_cancel(self, pending_action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute leave request cancellation action."""
        target_data = pending_action['target_data']
        leave_request_id = target_data['leave_request_id']
        
        # Get and update leave request
        leave_request = LeaveRequest.objects.get(id=leave_request_id)
        old_status = leave_request.status
        leave_request.status = 'CANCELLED'
        leave_request.save()
        
        result = {
            'success': True,
            'operation': 'cancelled',
            'employee_name': target_data['employee_name'],
            'leave_request_id': leave_request_id,
            'old_status': old_status,
            'new_status': 'CANCELLED',
            'message': f"Cancelled leave request for {target_data['employee_name']} from {leave_request.start_date.strftime('%B %d, %Y')} to {leave_request.end_date.strftime('%B %d, %Y')}"
        }
        
        return result
    
    def _revalidate_authorization(self, pending_action: Dict[str, Any], user):
        """Revalidate user authorization at execution time."""
        from .pipeline import derive_scope
        
        # Get fresh scope
        current_scope = derive_scope(user)
        stored_scope = pending_action.get('authorization_scope', {})
        
        # Basic authorization checks
        if not current_scope.get('unrestricted', False):
            # Verify user still has required scope
            target_data = pending_action.get('target_data', {})
            employee_id = target_data.get('employee_id')
            
            if employee_id:
                try:
                    employee = Employee.objects.get(id=employee_id)
                    if employee.section not in current_scope.get('sections', []):
                        raise CopilotError("scope_denied", "Authorization scope has changed", 403)
                    
                    if (current_scope.get('subsections') and 
                        employee.subsection not in current_scope.get('subsections', [])):
                        raise CopilotError("scope_denied", "Authorization scope has changed", 403)
                except Employee.DoesNotExist:
                    raise CopilotError("employee_not_found", "Target employee no longer exists")


class PendingActionManager:
    """Manages pending actions in session memory (avoiding database for now)."""
    
    def __init__(self):
        self.pending_actions = {}  # Session-based storage
    
    def store_pending_action(self, session_id: str, pending_action: Dict[str, Any]) -> str:
        """Store a pending action for user approval."""
        action_id = pending_action['action_id']
        
        if session_id not in self.pending_actions:
            self.pending_actions[session_id] = {}
        
        self.pending_actions[session_id][action_id] = {
            **pending_action,
            'created_at': timezone.now().isoformat(),
            'status': 'PENDING'
        }
        
        return action_id
    
    def get_pending_action(self, session_id: str, action_id: str) -> Dict[str, Any]:
        """Retrieve a pending action by session and action ID."""
        session_actions = self.pending_actions.get(session_id, {})
        action = session_actions.get(action_id)
        
        if not action:
            raise CopilotError("action_not_found", "Pending action not found or expired")
        
        # Check if expired
        created_at = datetime.fromisoformat(action['created_at'])
        expires_at = datetime.fromisoformat(action['expires_at'])
        
        if timezone.now() > expires_at.replace(tzinfo=timezone.get_current_timezone()):
            # Remove expired action
            del session_actions[action_id]
            raise CopilotError("action_expired", "Pending action has expired")
        
        return action
    
    def approve_action(self, session_id: str, action_id: str) -> Dict[str, Any]:
        """Mark an action as approved."""
        action = self.get_pending_action(session_id, action_id)
        
        if action['status'] != 'PENDING':
            raise CopilotError("action_not_pending", f"Action is already {action['status']}")
        
        action['status'] = 'APPROVED'
        action['approved_at'] = timezone.now().isoformat()
        
        return action
    
    def cancel_action(self, session_id: str, action_id: str) -> Dict[str, Any]:
        """Cancel a pending action."""
        action = self.get_pending_action(session_id, action_id)
        
        if action['status'] not in ['PENDING', 'APPROVED']:
            raise CopilotError("action_not_cancellable", f"Cannot cancel action in status {action['status']}")
        
        action['status'] = 'CANCELLED'
        
        return action
    
    def clear_session_actions(self, session_id: str):
        """Clear all pending actions for a session."""
        if session_id in self.pending_actions:
            del self.pending_actions[session_id]
    
    def get_session_actions(self, session_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all pending actions for a session."""
        return self.pending_actions.get(session_id, {})


# Create singleton instances
write_action_executor = WriteActionExecutor()
pending_action_manager = PendingActionManager()