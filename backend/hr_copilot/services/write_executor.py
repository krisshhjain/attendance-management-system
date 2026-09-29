"""Write action executor with human-in-the-loop approval for HR Copilot."""

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, time, timedelta
from typing import Dict, Any

from .pipeline import CopilotError
from ..models import CopilotPendingAction, CopilotActionAudit
from employees.models import Employee
from attendance.models import Attendance, AttendanceEvent, AttendanceCorrection
from leave_management.models import LeaveRequest
from system_logs.services import record_event


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
                    result = self._execute_attendance_update(pending_action, user)
                elif action_type == 'attendance_create':
                    result = self._execute_attendance_create(pending_action, user)
                elif action_type == 'leave_create':
                    result = self._execute_leave_create(pending_action)
                elif action_type == 'leave_cancel':
                    result = self._execute_leave_cancel(pending_action)
                elif action_type in {'leave_approve', 'leave_deny'}:
                    result = self._execute_leave_review(pending_action, user)
                else:
                    raise CopilotError("unsupported_action", f"Action type '{action_type}' not implemented")
                action_record = CopilotPendingAction.objects.select_for_update().get(action_id=pending_action['action_id'], user=user)
                new_state = {key: value for key, value in result.items() if key not in {'message'}}
                if pending_action.get('target_data', {}).get('reason'):
                    new_state['reason'] = pending_action['target_data']['reason']
                action_audit = CopilotActionAudit.objects.create(
                    pending_action=action_record, user=user, session_id=action_record.session_id,
                    action_type='write', intent=action_record.intent, operation=action_type,
                    target_description=action_record.description,
                    previous_state=pending_action.get('current_state') or {},
                    new_state=new_state,
                    success=True, explicit_confirmation=bool(action_record.approved_at),
                    authorization_scope=pending_action.get('authorization_scope') or {},
                )
                record_event(
                    event_type="COPILOT_ACTION_EXECUTED",
                    category="HR_COPILOT",
                    severity="INFO",
                    status="SUCCESS",
                    actor=user,
                    target={
                        "type": "hr_copilot.CopilotPendingAction",
                        "id": str(action_record.action_id),
                        "label": action_record.action_type,
                    },
                    message="HR Copilot action executed.",
                    source="HR_COPILOT",
                    metadata={"action_audit_id": action_audit.id},
                )
                return result
                    
        except CopilotError:
            raise
        except Exception as e:
            raise CopilotError("execution_failed", "The approved change could not be applied.") from e
    
    def _execute_attendance_update(self, pending_action: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute attendance update/create action."""
        target_data = pending_action['target_data']
        proposed_changes = pending_action['proposed_changes']
        
        employee_id = target_data['employee_id']
        target_date = datetime.fromisoformat(target_data['date']).date()
        target_status = proposed_changes['status']
        
        # Snapshot summary and source events before applying the explicit correction.
        events = list(AttendanceEvent.objects.filter(employee_id=employee_id, timestamp__date=target_date).order_by('timestamp'))
        previous_state = {
            'status': Attendance.objects.filter(employee_id=employee_id, date=target_date).values_list('status', flat=True).first(),
            'check_in': None, 'check_out': None, 'working_duration': None,
            'events': [{
                'id': event.id, 'event_type': event.event_type,
                'timestamp': event.timestamp.isoformat(), 'source': event.source,
                'shift_id': event.shift_id, 'latitude': event.latitude,
                'longitude': event.longitude, 'accuracy': event.accuracy,
                'distance': event.distance,
            } for event in events],
        }
        existing = Attendance.objects.filter(employee_id=employee_id, date=target_date).first()
        if existing:
            previous_state.update({
                'check_in': existing.check_in.isoformat() if existing.check_in else None,
                'check_out': existing.check_out.isoformat() if existing.check_out else None,
                'working_duration': str(existing.working_duration) if existing.working_duration else None,
            })

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
        
        AttendanceEvent.objects.filter(employee_id=employee_id, timestamp__date=target_date).delete()
        if target_status == 'PRESENT':
            local_date = target_date
            check_in = timezone.make_aware(datetime.combine(local_date, time.fromisoformat(target_data['check_in_time'])))
            check_out = timezone.make_aware(datetime.combine(local_date, time.fromisoformat(target_data['check_out_time'])))
            AttendanceEvent.objects.create(employee_id=employee_id, timestamp=check_in, event_type='CHECK_IN', source='ADMIN')
            AttendanceEvent.objects.create(employee_id=employee_id, timestamp=check_out, event_type='CHECK_OUT', source='ADMIN')
            attendance.check_in = check_in
            attendance.check_out = check_out
            attendance.working_duration = check_out - check_in
            attendance.leave_request = None
        else:
            attendance.check_in = None
            attendance.check_out = None
            attendance.working_duration = None
            attendance.leave_request = None
            for field in ('check_in_latitude', 'check_in_longitude', 'check_in_accuracy', 'check_in_distance', 'check_out_latitude', 'check_out_longitude', 'check_out_accuracy', 'check_out_distance'):
                setattr(attendance, field, None)
        attendance.status = target_status
        attendance.save()
        AttendanceCorrection.objects.create(
            attendance=attendance, admin_user=user, correction_type='HR_COPILOT',
            reason=target_data.get('reason') or 'HR Copilot approved attendance update',
            previous_data=previous_state,
        )
        result = {
            'success': True,
            'operation': 'updated' if not created else 'created',
            'employee_name': target_data['employee_name'],
            'date': target_date.isoformat(),
            'old_status': previous_state.get('status'),
            'status': target_status,
            'message': f"Attendance updated successfully for {target_data['employee_name']}.",
            'check_in': attendance.check_in.isoformat() if attendance.check_in else None,
            'check_out': attendance.check_out.isoformat() if attendance.check_out else None,
        }
        
        return result
    
    def _execute_attendance_create(self, pending_action: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute attendance creation action."""
        # Same as update but ensures creation
        return self._execute_attendance_update(pending_action, user)
    
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

    def _execute_leave_review(self, pending_action: Dict[str, Any], user) -> Dict[str, Any]:
        """Use the leave app's existing review services and attendance updates."""
        target_data = pending_action['target_data']
        proposed_changes = pending_action['proposed_changes']
        try:
            leave_request = LeaveRequest.objects.select_related('employee', 'leave_type').get(
                id=target_data['leave_request_id'],
                employee_id=target_data['employee_id'],
            )
        except LeaveRequest.DoesNotExist as error:
            raise CopilotError("leave_request_not_found", "The leave request no longer exists") from error
        if leave_request.status != 'PENDING':
            raise CopilotError("leave_request_changed", "This leave request is no longer pending review")

        from leave_management.services import approve_leave_request, deny_leave_request
        try:
            if pending_action['action_type'] == 'leave_approve':
                reviewed = approve_leave_request(
                    leave_request, user, remarks=proposed_changes.get('reviewer_remarks', ''),
                )
            else:
                reviewed = deny_leave_request(
                    leave_request, user, remarks=proposed_changes.get('reviewer_remarks', ''),
                )
        except Exception as error:
            raise CopilotError("leave_review_failed", "The leave request could not be reviewed. It may have changed since the approval preview.") from error

        status = reviewed.status
        return {
            'success': True,
            'operation': status.lower(),
            'employee_name': target_data['employee_name'],
            'leave_request_id': reviewed.id,
            'start_date': reviewed.start_date.isoformat(),
            'end_date': reviewed.end_date.isoformat(),
            'status': status,
            'message': f"{status.title()} {target_data['employee_name']}'s leave request from {reviewed.start_date:%B %d, %Y} to {reviewed.end_date:%B %d, %Y}.",
        }
    
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
    """Persist approval actions so they survive restarts and multiple workers."""

    def store_pending_action(self, session_id: str, pending_action: Dict[str, Any]) -> str:
        """Store a pending action in the database for the owning user."""
        action_id = pending_action['action_id']
        CopilotPendingAction.objects.create(
            action_id=action_id,
            session_id=session_id,
            user_id=pending_action['user_id'],
            conversation_id=pending_action.get('conversation_id'),
            action_type=pending_action['action_type'],
            intent=pending_action['intent'],
            source=pending_action.get('source', 'hr_copilot'),
            target_data=pending_action['target_data'],
            proposed_changes=pending_action['proposed_changes'],
            current_state=pending_action.get('current_state'),
            validated=pending_action.get('validated', False),
            authorization_scope=pending_action.get('authorization_scope'),
            requires_confirmation=pending_action.get('requires_confirmation', True),
            status=pending_action.get('status', 'PENDING'),
            validation_errors=pending_action.get('validation_errors'),
            expires_at=pending_action['expires_at'],
            description=pending_action['description'],
            warning_message=pending_action.get('warning_message'),
        )
        return action_id

    @staticmethod
    def _as_dict(action):
        return {
            'action_id': str(action.action_id),
            'session_id': action.session_id,
            'user_id': action.user_id,
            'conversation_id': action.conversation_id,
            'action_type': action.action_type,
            'intent': action.intent,
            'source': action.source,
            'target_data': action.target_data,
            'proposed_changes': action.proposed_changes,
            'current_state': action.current_state or {},
            'validated': action.validated,
            'authorization_scope': action.authorization_scope or {},
            'requires_confirmation': action.requires_confirmation,
            'status': action.status,
            'validation_errors': action.validation_errors or [],
            'created_at': action.created_at.isoformat(),
            'expires_at': action.expires_at.isoformat(),
            'description': action.description,
            'warning_message': action.warning_message,
        }

    def get_pending_action(self, session_id: str, action_id: str, user_id: int):
        """Retrieve only an action owned by this user and current copilot session."""
        try:
            action = CopilotPendingAction.objects.get(
                action_id=action_id, session_id=session_id, user_id=user_id,
            )
        except (CopilotPendingAction.DoesNotExist, ValueError, ValidationError):
            raise CopilotError("action_not_found", "Pending action not found or expired")
        if action.is_expired:
            if action.status == 'PENDING':
                action.status = 'EXPIRED'
                action.save(update_fields=['status'])
                record_event(
                    event_type="COPILOT_ACTION_EXPIRED",
                    category="HR_COPILOT",
                    severity="WARNING",
                    status="FAILED",
                    actor=action.user,
                    target=action,
                    message="HR Copilot action expired.",
                    source="HR_COPILOT",
                    metadata={"action_id": str(action.action_id)},
                )
            raise CopilotError("action_expired", "Pending action has expired")
        return action

    def approve_action(self, session_id: str, action_id: str, user_id: int):
        expired = False
        result = None
        with transaction.atomic():
            action = CopilotPendingAction.objects.select_for_update().filter(
                action_id=action_id, session_id=session_id, user_id=user_id,
            ).first()
            if not action:
                raise CopilotError("action_not_found", "Pending action not found or expired")
            if action.is_expired:
                action.status = 'EXPIRED'
                action.save(update_fields=['status'])
                expired = True
            elif action.status != 'PENDING' or not action.validated:
                raise CopilotError("action_not_pending", "This action is no longer awaiting approval")
            else:
                action.mark_approved()
                result = self._as_dict(action)
        if expired:
            record_event(
                event_type="COPILOT_ACTION_EXPIRED",
                category="HR_COPILOT",
                severity="WARNING",
                status="FAILED",
                actor=action.user,
                target=action,
                message="HR Copilot action expired.",
                source="HR_COPILOT",
                metadata={"action_id": str(action.action_id)},
            )
            raise CopilotError("action_expired", "Pending action has expired")
        return result

    def cancel_action(self, session_id: str, action_id: str, user_id: int):
        action = CopilotPendingAction.objects.filter(action_id=action_id, session_id=session_id, user_id=user_id).first()
        if not action:
            raise CopilotError("action_not_found", "Pending action not found or expired")
        if action.status not in {'PENDING', 'AWAITING_INFORMATION'}:
            raise CopilotError("action_not_cancellable", f"Cannot cancel action in status {action.status}")
        action.cancel()
        return self._as_dict(action)

    def get_awaiting_action(self, session_id: str, conversation_id: str, user_id: int):
        action = CopilotPendingAction.objects.filter(
            session_id=session_id, conversation_id=conversation_id, user_id=user_id,
            status='AWAITING_INFORMATION', expires_at__gt=timezone.now(),
        ).first()
        return self._as_dict(action) if action else None

    def update_awaiting_action(self, action_id: str, user_id: int, session_id: str, updates):
        with transaction.atomic():
            action = CopilotPendingAction.objects.select_for_update().filter(
                action_id=action_id, user_id=user_id, session_id=session_id,
                status='AWAITING_INFORMATION', expires_at__gt=timezone.now(),
            ).first()
            if not action:
                raise CopilotError("action_not_pending", "This follow-up no longer matches an active action")
            for field in ('target_data', 'proposed_changes', 'current_state', 'validation_errors', 'description', 'validated', 'status'):
                if field in updates:
                    setattr(action, field, updates[field])
            action.save(update_fields=['target_data', 'proposed_changes', 'current_state', 'validation_errors', 'description', 'validated', 'status'])
            return self._as_dict(action)

    def mark_executed(self, action_id: str, user_id: int, session_id: str, result):
        CopilotPendingAction.objects.filter(action_id=action_id, user_id=user_id, session_id=session_id, status='APPROVED').update(
            status='EXECUTED', executed_at=timezone.now(), execution_result=result,
        )

    def mark_failed(self, action_id: str, user_id: int, session_id: str, error):
        CopilotPendingAction.objects.filter(action_id=action_id, user_id=user_id, session_id=session_id, status='APPROVED').update(
            status='FAILED', executed_at=timezone.now(), execution_error=str(error)[:2000],
        )

    def get_session_actions(self, session_id: str, user_id: int):
        actions = CopilotPendingAction.objects.filter(
            session_id=session_id, user_id=user_id, status__in=['PENDING', 'AWAITING_INFORMATION'], expires_at__gt=timezone.now(),
        )
        return {str(action.action_id): self._as_dict(action) for action in actions}


# Create singleton instances
write_action_executor = WriteActionExecutor()
pending_action_manager = PendingActionManager()
