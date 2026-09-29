"""Write action planning and approval workflow for HR Copilot."""

from datetime import datetime, timedelta, time
from typing import Dict, Any, Optional
import uuid

from django.utils import timezone
from django.db import transaction

from .pipeline import CopilotError, derive_scope
from .employee_resolver import employee_resolver
from employees.models import Employee
from attendance.models import Attendance, AttendanceEvent
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
        if intent['intent'] in {'attendance_update', 'attendance_create', 'leave_create'}:
            entities = intent.get('entities', {})
            if not any(entities.get(key) for key in ('employee_id', 'employee_name', 'employee_email')):
                return self._plan_missing_employee(intent, user, scope, session_id)
        
        # Plan the specific action based on intent
        if intent['intent'] == 'attendance_update':
            return self._plan_attendance_update(intent, user, scope, session_id)
        elif intent['intent'] == 'attendance_create':
            return self._plan_attendance_update(intent, user, scope, session_id)
        elif intent['intent'] == 'leave_create':
            return self._plan_leave_create(intent, user, scope, session_id)
        elif intent['intent'] == 'leave_cancel':
            return self._plan_leave_cancel(intent, user, scope, session_id)
        elif intent['intent'] in {'leave_approve', 'leave_deny'}:
            return self._plan_leave_review(intent, user, scope, session_id)
        else:
            raise CopilotError("unsupported_write", f"Write action '{intent['intent']}' not yet implemented")
    
    def _plan_attendance_update(self, intent: Dict[str, Any], user, scope: Dict, session_id: str) -> Dict[str, Any]:
        """Plan an attendance update action."""
        entities = intent.get('entities', {})
        
        # Resolve employee
        employee_resolution = self._resolve_target_employee(entities, user, scope)
        
        # Resolve target date
        target_date = self._resolve_target_date(entities)
        if not entities.get('date_range') and not entities.get('temporal_expression'):
            raise CopilotError("attendance_date_required", "Which date should I use for this attendance change?")
        
        # Resolve target status with fallback logic
        target_status = entities.get('target_status', entities.get('attendance_status'))
        
        # Fallback: try to infer from query text if not explicitly provided
        if not target_status:
            # Get the original query text if available
            query_text = intent.get('original_query', '').lower()
            if 'absent' in query_text or 'as absent' in query_text:
                target_status = 'ABSENT'
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
            'absent': 'ABSENT',
            'ABSENT': 'ABSENT',
            'present': 'PRESENT', 
            'PRESENT': 'PRESENT',
            'incomplete': 'INCOMPLETE',
            'INCOMPLETE': 'INCOMPLETE',
            'leave': 'LEAVE',
            'LEAVE': 'LEAVE'
        }
        
        if target_status.lower() in status_mapping:
            target_status = status_mapping[target_status.lower()]
        else:
            target_status = target_status.upper()
        
        # Validate target status
        valid_statuses = ['PRESENT', 'INCOMPLETE', 'ABSENT', 'LEAVE']
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
            'date': target_date.isoformat(),
            'check_in': current_attendance.check_in.isoformat() if current_attendance and current_attendance.check_in else None,
            'check_out': current_attendance.check_out.isoformat() if current_attendance and current_attendance.check_out else None,
            'working_duration': str(current_attendance.working_duration) if current_attendance and current_attendance.working_duration else None,
            'events': [
                {
                    'id': event.id, 'event_type': event.event_type,
                    'timestamp': event.timestamp.isoformat(), 'source': event.source,
                    'shift_id': event.shift_id, 'latitude': event.latitude,
                    'longitude': event.longitude, 'accuracy': event.accuracy,
                    'distance': event.distance,
                }
                for event in AttendanceEvent.objects.filter(employee_id=employee_resolution['employee_id'], timestamp__date=target_date).order_by('timestamp')
            ],
        }
        
        missing = []
        check_in = self._normalize_time(entities.get('check_in_time'), checkout=False) if target_status == 'PRESENT' else None
        check_out = self._normalize_time(entities.get('check_out_time'), checkout=True) if target_status == 'PRESENT' else None
        if target_status == 'PRESENT':
            if not check_in: missing.append('check_in_time')
            if not check_out: missing.append('check_out_time')
            if check_in and check_out and check_out <= check_in:
                raise CopilotError("invalid_attendance_time", "Check-out must be later than check-in.")
        reason = (entities.get('reason') or '').strip()
        original = (intent.get('original_query') or '').casefold()
        if target_status == 'LEAVE' and not reason:
            missing.append('reason')
        if missing and 'employee_name' in entities:
            missing.remove('employee_name')
        employee_label = employee_resolution['employee_name']
        date_label = f"{target_date.day} {target_date.strftime('%B')}"
        timing_question = f"Sure. What check-in and check-out times should I use for {employee_label} on {date_label}?"

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
                'target_status': target_status,
                'check_in_time': check_in,
                'check_out_time': check_out,
                'reason': reason,
            },
            'proposed_changes': {
                'status': target_status,
                'operation': 'update' if current_attendance else 'create',
                'check_in_time': check_in,
                'check_out_time': check_out,
                'reason': reason,
            },
            'current_state': current_state,
            'validated': not missing,
            'status': 'AWAITING_INFORMATION' if missing else 'PENDING',
            'validation_errors': missing or None,
            'authorization_scope': scope,
            'requires_confirmation': True,
            'description': timing_question if set(missing) == {'check_in_time', 'check_out_time'} else (f"Change {employee_resolution['employee_name']}'s attendance on {target_date.strftime('%B %d, %Y')} to {target_status}" if not missing else self._missing_question(employee_resolution['employee_name'], missing)),
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
        
        reason = (entities.get('reason') or '').strip()
        missing = ['reason'] if not reason else []
        
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
            'validated': not missing,
            'status': 'AWAITING_INFORMATION' if missing else 'PENDING',
            'validation_errors': missing or None,
            'authorization_scope': scope,
            'requires_confirmation': True,
            'description': f"Please provide the reason for {employee_resolution['employee_name']}'s leave." if missing else f"Create {duration_days}-day leave request for {employee_resolution['employee_name']} starting {start_date.strftime('%B %d, %Y')}: {reason}",
            'expires_at': timezone.now() + timedelta(minutes=10)
        }
        
        return pending_action
    
    def _plan_leave_cancel(self, intent: Dict[str, Any], user, scope: Dict, session_id: str) -> Dict[str, Any]:
        """Plan a leave cancellation action."""
        entities = intent.get('entities', {})
        
        # If no specific employee mentioned, assume user wants to cancel their own leave
        if not any(entities.get(key) for key in ('employee_name', 'employee_email', 'employee_id')):
            try:
                entities = {**entities, 'employee_id': user.employee.id}
            except Employee.DoesNotExist:
                raise CopilotError("no_employee_profile", "Cannot find your employee profile")
        employee_resolution = self._resolve_target_employee(entities, user, scope)
        employee_id = employee_resolution['employee_id']
        employee_name = employee_resolution['employee_name']
        
        # Find recent pending/approved leave requests
        recent_leaves = LeaveRequest.objects.filter(
            employee_id=employee_id,
            status__in=['PENDING', 'APPROVED'],
            start_date__gte=timezone.now().date()
        ).order_by('-submitted_at')[:5]
        
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
                'duration_days': float(leave_request.duration_days)
            },
            'validated': True,
            'authorization_scope': scope,
            'requires_confirmation': True,
            'description': f"Cancel {employee_name}'s leave request from {leave_request.start_date.strftime('%B %d, %Y')} to {leave_request.end_date.strftime('%B %d, %Y')}",
            'warning_message': "This action cannot be undone. The leave request will be permanently cancelled.",
            'expires_at': timezone.now() + timedelta(minutes=10)
        }
        
        return pending_action

    def _plan_leave_review(self, intent: Dict[str, Any], user, scope: Dict, session_id: str) -> Dict[str, Any]:
        """Prepare one explicitly targeted pending leave for approval or denial."""
        entities = intent.get('entities', {})
        if not any(entities.get(key) for key in ('employee_name', 'employee_email', 'employee_id')):
            raise CopilotError("employee_required", "Specify the employee whose leave request should be reviewed.")

        employee = self._resolve_target_employee(entities, user, scope)
        requests = LeaveRequest.objects.filter(employee_id=employee['employee_id'], status='PENDING').select_related('leave_type')
        date_range = entities.get('date_range')
        if date_range:
            requests = requests.filter(start_date__lte=date_range['end'], end_date__gte=date_range['start'])
        matches = list(requests.order_by('-submitted_at')[:2])
        if not matches:
            raise CopilotError("leave_request_not_found", f"No pending leave request was found for {employee['employee_name']} with those dates.")
        if len(matches) != 1:
            raise CopilotError("leave_request_ambiguous", "More than one pending leave request matched. Specify the requested leave dates.")

        leave_request = matches[0]
        target_status = 'APPROVED' if intent['intent'] == 'leave_approve' else 'DENIED'
        remarks = (entities.get('reason') or '').strip()
        if target_status == 'DENIED' and not remarks:
            raise CopilotError("review_reason_required", "Provide a reason for denying this leave request.")

        return {
            'action_id': str(uuid.uuid4()),
            'session_id': session_id,
            'user_id': user.id,
            'action_type': intent['intent'],
            'intent': intent['intent'],
            'source': intent.get('source', 'leave'),
            'target_data': {
                'employee_id': employee['employee_id'],
                'employee_name': employee['employee_name'],
                'leave_request_id': leave_request.id,
            },
            'proposed_changes': {'status': target_status, 'reviewer_remarks': remarks},
            'current_state': {
                'status': leave_request.status,
                'leave_type': leave_request.leave_type.name,
                'start_date': leave_request.start_date.isoformat(),
                'end_date': leave_request.end_date.isoformat(),
                'duration_days': float(leave_request.duration_days),
            },
            'validated': True,
            'authorization_scope': scope,
            'requires_confirmation': True,
            'description': f"{target_status.title()} {employee['employee_name']}'s {leave_request.leave_type.name} leave from {leave_request.start_date:%B %d, %Y} to {leave_request.end_date:%B %d, %Y}",
            'warning_message': "This review also updates attendance records for the requested leave dates." if target_status == 'APPROVED' else None,
            'expires_at': timezone.now() + timedelta(minutes=10),
        }
    
    def _resolve_target_employee(self, entities: Dict, user, scope: Dict) -> Dict[str, Any]:
        """Resolve the target employee for the action."""
        employee_name = entities.get('employee_name')
        employee_email = entities.get('employee_email')

        if entities.get('employee_id'):
            employee = Employee.objects.select_related('user').filter(pk=entities['employee_id']).first()
            if employee is None:
                raise CopilotError("employee_not_found", "Employee not found")
        elif employee_name or employee_email:
            resolution = employee_resolver.resolve_employee(name=employee_name, email=employee_email)
            if resolution.status == 'not_found':
                raise CopilotError("employee_not_found", "Employee not found")
            if resolution.status == 'ambiguous':
                raise CopilotError("employee_ambiguous", "Multiple employees match. Please provide email address.")
            employee = Employee.objects.select_related('user').filter(id=resolution.employee_id).first()
            if employee is None:
                raise CopilotError("employee_not_found", "Employee not found")
        else:
            try:
                employee = Employee.objects.select_related('user').get(user=user)
            except Employee.DoesNotExist as error:
                raise CopilotError("employee_required", "Employee name or email is required") from error

        # Verify every resolution path, including interpreter-resolved IDs, is scoped.
        if not scope['unrestricted']:
            if employee.section not in scope['sections']:
                raise CopilotError("scope_denied", "You don't have access to this employee", 403)
            if scope['subsections'] and employee.subsection not in scope['subsections']:
                raise CopilotError("scope_denied", "You don't have access to this employee", 403)
        
        return {
            'employee_id': employee.id,
            'employee_name': f"{employee.user.first_name} {employee.user.last_name}"
        }

    @staticmethod
    def _normalize_time(value, checkout=False):
        if not value:
            return None
        text = str(value).strip().upper().replace('.', '')
        for fmt in ('%H:%M', '%I:%M %p', '%I %p', '%H:%M:%S'):
            try:
                return datetime.strptime(text, fmt).strftime('%H:%M')
            except ValueError:
                continue
        if text.isdigit() and 0 <= int(text) <= 23:
            hour = int(text)
            if checkout and 1 <= hour <= 11:
                hour += 12
            return time(hour, 0).strftime('%H:%M')
        return None

    @staticmethod
    def _missing_question(employee_name, missing):
        if {'check_in_time', 'check_out_time'}.issubset(missing):
            return f"Sure. What check-in and check-out times should I use for {employee_name}?"
        if 'check_in_time' in missing:
            return f"What check-in time should I use for {employee_name}?"
        if 'check_out_time' in missing:
            return f"What check-out time should I use for {employee_name}?"
        if 'employee_name' in missing:
            return "Which employee should I update? Please provide their name or work email."
        if 'employee_email' in missing:
            return "Several employees match that name. Which work email should I use?"
        if 'reason' in missing:
            return f"Please provide the reason for {employee_name}'s leave."
        return f"What check-in and check-out times should I use for {employee_name}?"

    def _plan_missing_employee(self, intent, user, scope, session_id):
        entities = intent.get('entities', {})
        intent_name = intent['intent']
        target_date = self._resolve_target_date(entities)
        if not entities.get('date_range') and not entities.get('temporal_expression'):
            raise CopilotError("attendance_date_required", "Which date should I use for this attendance change?")
        original = (intent.get('original_query') or '').casefold()
        target_status = entities.get('target_status', entities.get('attendance_status'))
        if not target_status:
            target_status = 'ABSENT' if 'absent' in original else 'LEAVE' if 'leave' in original else 'PRESENT'
        target_status = {'ABSENT': 'ABSENT', 'LEAVE': 'LEAVE', 'PRESENT': 'PRESENT', 'INCOMPLETE': 'INCOMPLETE'}.get(str(target_status).upper(), str(target_status).upper())
        reason = (entities.get('reason') or '').strip()
        target_data = {
            'employee_id': None, 'employee_name': None,
            'date': target_date.isoformat(), 'start_date': target_date.isoformat(),
            'end_date': target_date.isoformat(), 'target_status': target_status,
            'check_in_time': self._normalize_time(entities.get('check_in_time')),
            'check_out_time': self._normalize_time(entities.get('check_out_time'), checkout=True),
            'reason': reason, 'duration_days': entities.get('duration_days', 1),
        }
        missing = ['employee_name']
        if intent_name != 'leave_create' and target_status == 'PRESENT':
            if not target_data['check_in_time']: missing.append('check_in_time')
            if not target_data['check_out_time']: missing.append('check_out_time')
        if (intent_name == 'leave_create' or target_status == 'LEAVE') and not reason:
            missing.append('reason')
        return {
            'action_id': str(uuid.uuid4()), 'session_id': session_id, 'user_id': user.id,
            'action_type': 'leave_create' if intent_name == 'leave_create' else 'attendance_update',
            'intent': intent_name, 'source': intent.get('source', 'attendance'),
            'target_data': target_data,
            'proposed_changes': {'status': target_status, 'operation': 'update', **{key: target_data[key] for key in ('check_in_time', 'check_out_time', 'reason')}},
            'current_state': {}, 'validated': False,
            'status': 'AWAITING_INFORMATION', 'validation_errors': missing,
            'authorization_scope': scope, 'requires_confirmation': True,
            'description': self._missing_question('', missing),
            'expires_at': timezone.now() + timedelta(minutes=10),
        }

    @staticmethod
    def _attendance_description(employee_name, target_date, status, check_in, check_out, reason):
        details = f"Status: {status}"
        if status == 'PRESENT':
            details += f"; check-in {check_in}; check-out {check_out}"
        elif status == 'LEAVE':
            details += "; check-in cleared; check-out cleared"
            if reason:
                details += f"; reason: {reason}"
        elif status == 'ABSENT':
            details += "; check-in cleared; check-out cleared"
        return f"Confirm attendance for {employee_name} on {target_date:%B %d, %Y}. {details}."
    
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
