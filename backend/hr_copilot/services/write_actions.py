"""Write action planning and approval workflow for HR Copilot."""

from datetime import datetime, timedelta, time
from typing import Dict, Any, Optional
import uuid

from django.utils import timezone
from django.db import transaction

from .pipeline import CopilotError, derive_scope
from .employee_resolver import employee_resolver
from employees.models import Employee
from attendance.models import Attendance, AttendanceEvent, RegularizationRequest, Shift
from leave_management.models import LeaveRequest, LeaveType


class WriteActionPlanner:
    """Plans and validates write actions for HR Copilot."""
    
    def __init__(self):
        self.write_intents = {
            'attendance_update', 'attendance_create', 'leave_create', 
            'leave_cancel', 'leave_approve', 'leave_deny'
            , 'attendance_force_checkout', 'regularization_create', 'regularization_approve',
            'regularization_reject', 'employee_shift_assign', 'employee_status_update'
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
        elif intent['intent'] == 'attendance_force_checkout':
            return self._plan_force_checkout(intent, user, scope, session_id)
        elif intent['intent'] == 'regularization_create':
            return self._plan_regularization_create(intent, user, scope, session_id)
        elif intent['intent'] in {'regularization_approve', 'regularization_reject'}:
            return self._plan_regularization_review(intent, user, scope, session_id)
        elif intent['intent'] == 'employee_shift_assign':
            return self._plan_shift_assignment(intent, user, scope, session_id)
        elif intent['intent'] == 'employee_status_update':
            return self._plan_employee_status(intent, user, scope, session_id)
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
        
        if not target_status and intent['intent'] != 'attendance_reset':
            raise CopilotError("missing_status", "Target attendance status is required. Please specify 'present', 'absent', or 'incomplete'.")
            
        if not scope.get('unrestricted'):
            if target_date < timezone.localdate():
                raise CopilotError("admin_only", "Only administrators can edit past attendance records.", 403)
            if intent['intent'] == 'attendance_reset':
                raise CopilotError("admin_only", "Only administrators can reset attendance records.", 403)
        
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

        if target_status == "ABSENT":
            from holidays.services import attendance_required, get_day_classification
            if not attendance_required(target_date):
                day = get_day_classification(target_date)
                raise CopilotError(
                    "attendance_not_required",
                    f"Cannot mark an employee absent on a {day['day_type'].lower()} date.",
                )
        
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
        
        leave_type_value = entities.get('leave_type')
        leave_types = LeaveType.objects.filter(is_active=True)
        if leave_type_value:
            leave_types = leave_types.filter(code__iexact=str(leave_type_value)) | LeaveType.objects.filter(is_active=True, name__iexact=str(leave_type_value))
        leave_type_matches = list(leave_types.distinct()[:2])
        if not leave_type_matches:
            raise CopilotError("no_leave_types", "No leave types are configured in the system")
        if len(leave_type_matches) > 1:
            raise CopilotError("leave_type_ambiguous", "Specify the leave type code or name.")
        leave_type = leave_type_matches[0]
        
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
            start_date__gte=timezone.localdate()
        ).order_by('-submitted_at')[:5]

        if entities.get('request_id'):
            recent_leaves = LeaveRequest.objects.filter(
                pk=entities['request_id'], employee_id=employee_id,
                status__in=['PENDING', 'APPROVED'],
            )
        
        if not recent_leaves.exists():
            raise CopilotError("no_leave_requests", f"No pending or approved leave requests found for {employee_name}")
        
        if not entities.get('request_id') and recent_leaves.count() > 1:
            raise CopilotError('leave_request_ambiguous', 'More than one leave request matched. Specify the request ID or dates.')
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
        if not any(entities.get(key) for key in ('employee_name', 'employee_email', 'employee_id')) and entities.get('request_id'):
            request = LeaveRequest.objects.select_related('employee').filter(pk=entities['request_id']).first()
            if request:
                entities = {**entities, 'employee_id': request.employee_id}
        if not any(entities.get(key) for key in ('employee_name', 'employee_email', 'employee_id')):
            raise CopilotError("employee_required", "Specify the employee whose leave request should be reviewed.")

        employee = self._resolve_target_employee(entities, user, scope)
        requests = LeaveRequest.objects.filter(employee_id=employee['employee_id'], status='PENDING').select_related('leave_type')
        if entities.get('request_id'):
            requests = requests.filter(pk=entities['request_id'])
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

    def _base_pending(self, intent, user, session_id, action_type, target_data, proposed, current, description, scope, warning=None, missing=None):
        return {
            'action_id': str(uuid.uuid4()), 'session_id': session_id, 'user_id': user.id,
            'action_type': action_type, 'intent': intent['intent'], 'source': intent.get('source', 'hr_copilot'),
            'target_data': target_data, 'proposed_changes': proposed, 'current_state': current,
            'validated': not missing, 'status': 'AWAITING_INFORMATION' if missing else 'PENDING',
            'validation_errors': missing or None, 'authorization_scope': scope, 'requires_confirmation': True,
            'description': description, 'warning_message': warning,
            'expires_at': timezone.now() + timedelta(minutes=10),
        }

    def _plan_force_checkout(self, intent, user, scope, session_id):
        entities = intent.get('entities', {})
        employee = self._resolve_target_employee(entities, user, scope)
        target_date = self._resolve_target_date(entities)
        attendance = Attendance.objects.filter(employee_id=employee['employee_id'], date=target_date).first()
        events = list(AttendanceEvent.objects.filter(employee_id=employee['employee_id'], timestamp__date=target_date).order_by('timestamp', 'id'))
        if not events or events[-1].event_type != 'CHECK_IN':
            raise CopilotError('no_active_checkin', 'No active check-in was found for that employee on that date.')
        return self._base_pending(intent, user, session_id, 'attendance_force_checkout',
            {'employee_id': employee['employee_id'], 'employee_name': employee['employee_name'], 'date': target_date.isoformat()},
            {'operation': 'force_checkout'},
            {'status': attendance.status if attendance else None, 'last_event': events[-1].timestamp.isoformat()},
            f"Force check-out for {employee['employee_name']} on {target_date:%B %d, %Y} at the current time.", scope,
            warning='This creates an ADMIN checkout event and recomputes attendance.')

    def _plan_regularization_create(self, intent, user, scope, session_id):
        entities = intent.get('entities', {})
        employee = self._resolve_target_employee(entities, user, scope)
        target_date = self._resolve_target_date(entities)
        reason = (entities.get('reason') or '').strip()
        missing = ['reason'] if not reason else []
        request_type = str(entities.get('request_type') or 'INCORRECT_ATTENDANCE').upper()
        valid_types = {key for key, _ in RegularizationRequest.REQUEST_TYPES}
        if request_type not in valid_types:
            raise CopilotError('invalid_request_type', 'Specify a supported regularization request type.')
        existing = Attendance.objects.filter(employee_id=employee['employee_id'], date=target_date).first()
        check_in = self._normalize_time(entities.get('check_in_time'))
        check_out = self._normalize_time(entities.get('check_out_time'), checkout=True)
        if entities.get('check_in_time') and not check_in or entities.get('check_out_time') and not check_out:
            raise CopilotError('invalid_regularization_time', 'Use valid check-in and check-out times.')
        if check_in and check_out and check_out <= check_in:
            raise CopilotError('invalid_regularization_time', 'Check-out must be later than check-in.')
        target = {'employee_id': employee['employee_id'], 'employee_name': employee['employee_name'], 'attendance_date': target_date.isoformat(),
                  'request_type': request_type, 'reason': reason,
                  'requested_check_in': check_in, 'requested_check_out': check_out}
        return self._base_pending(intent, user, session_id, 'regularization_create', target,
            {'operation': 'create', 'request_type': request_type},
            {'attendance_exists': bool(existing), 'status': 'PENDING'},
            f"Submit a {request_type.replace('_', ' ').title()} regularization request for {employee['employee_name']} on {target_date:%B %d, %Y}.", scope, missing=missing)

    def _plan_regularization_review(self, intent, user, scope, session_id):
        entities = intent.get('entities', {})
        employee_id = entities.get('employee_id')
        qs = RegularizationRequest.objects.select_related('employee__user').filter(status='PENDING')
        if entities.get('request_id'):
            qs = qs.filter(pk=entities['request_id'])
        elif employee_id:
            qs = qs.filter(employee_id=employee_id)
        else:
            raise CopilotError('request_required', 'Specify the regularization request ID or employee.')
        if entities.get('date_range'):
            qs = qs.filter(attendance_date__range=(entities['date_range']['start'], entities['date_range']['end']))
        matches = list(qs.order_by('-created_at')[:2])
        if not matches:
            raise CopilotError('regularization_not_found', 'No pending regularization request matched that target.')
        if len(matches) > 1:
            raise CopilotError('regularization_ambiguous', 'More than one pending regularization matched. Specify the request ID or date.')
        req = matches[0]
        if req.days.exists():
            raise CopilotError('unsupported_grouped_regularization', 'Grouped regularization requests must be reviewed in the regularization screen.')
        self._resolve_target_employee({'employee_id': req.employee_id}, user, scope)
        reason = (entities.get('reason') or '').strip()
        missing = ['reason'] if intent['intent'] == 'regularization_reject' and not reason else []
        return self._base_pending(intent, user, session_id, intent['intent'],
            {'request_id': req.id, 'employee_id': req.employee_id, 'employee_name': req.employee.user.get_full_name().strip() or req.employee.user.email},
            {'status': 'REJECTED' if intent['intent'] == 'regularization_reject' else 'APPROVED', 'reason': reason},
            {'status': req.status, 'attendance_date': req.attendance_date.isoformat()},
            f"{'Reject' if intent['intent'] == 'regularization_reject' else 'Approve'} regularization request #{req.id} for {req.employee.user.get_full_name().strip() or req.employee.user.email}.", scope, missing=missing)

    def _plan_shift_assignment(self, intent, user, scope, session_id):
        entities = intent.get('entities', {})
        employee = self._resolve_target_employee(entities, user, scope)
        shift = None
        if entities.get('shift_id'):
            shift = Shift.objects.filter(pk=entities['shift_id']).first()
        elif entities.get('shift_name'):
            shift = Shift.objects.filter(name__iexact=entities['shift_name']).first()
        if not shift:
            raise CopilotError('shift_not_found', 'Specify a valid shift ID or shift name.')
        target = Employee.objects.select_related('shift').get(pk=employee['employee_id'])
        if shift.employment_type and shift.employment_type != target.employment_type:
            raise CopilotError('shift_incompatible', 'That shift is configured for a different employment type.')
        return self._base_pending(intent, user, session_id, 'employee_shift_assign',
            {'employee_id': target.id, 'employee_name': employee['employee_name'], 'shift_id': shift.id, 'shift_name': shift.name},
            {'shift_id': shift.id, 'shift_name': shift.name},
            {'shift_id': target.shift_id, 'shift_name': target.shift.name if target.shift else None},
            f"Assign {shift.name} ({shift.code}) to {employee['employee_name']}.", scope)

    def _plan_employee_status(self, intent, user, scope, session_id):
        entities = intent.get('entities', {})
        employee = self._resolve_target_employee(entities, user, scope)
        if 'is_active' not in entities:
            raise CopilotError('status_required', 'Specify whether the employee should be activated or deactivated.')
        target = Employee.objects.get(pk=employee['employee_id'])
        desired = bool(entities['is_active'])
        return self._base_pending(intent, user, session_id, 'employee_status_update',
            {'employee_id': target.id, 'employee_name': employee['employee_name'], 'is_active': desired},
            {'is_active': desired}, {'is_active': target.is_active},
            f"{'Activate' if desired else 'Deactivate'} employee {employee['employee_name']}.", scope,
            warning='Deactivating an employee removes their active employee access.')
    
    def _resolve_target_employee(self, entities: Dict, user, scope: Dict) -> Dict[str, Any]:
        """Resolve the target employee for the action."""
        employee_name = entities.get('employee_name')
        employee_email = entities.get('employee_email')

        if entities.get('employee_id'):
            employee = Employee.objects.select_related('user').filter(pk=entities['employee_id']).first()
            if employee is None:
                raise CopilotError("employee_not_found", "Employee not found")
        elif employee_name or employee_email:
            resolution = employee_resolver.resolve_employee(user=user, name=employee_name, email=employee_email)
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
            from accounts.scope_service import employee_in_manager_scope
            if not employee_in_manager_scope(user, employee):
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
        
        today = timezone.localdate()
        
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
