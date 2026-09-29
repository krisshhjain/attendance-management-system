import logging
import time
import uuid
from datetime import datetime

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CopilotQueryAudit, CopilotPendingAction, CopilotActionAudit
from leave_management.models import LeaveType
from attendance.models import Attendance
from .services.conversation import append_message, apply_context, load_context, load_messages, save_context, update_action_message
from .services.pipeline import (
    CopilotError,
    analyze_question,
    build_sql,
    derive_scope,
    execute_query,
    generate_answer,
    plan_query,
    serialize_result,
    validate_sql,
)
from .services.providers import provider_health
from .services.tools import hr_tools
from .services.llm import generate_natural_answer
from .services.write_actions import write_action_planner
from .services.write_executor import write_action_executor, pending_action_manager
from .services.llm import extract_pending_action_fields
from system_logs.services import record_event

logger = logging.getLogger(__name__)


def _copilot_action_target(action_id, action_type=""):
    return {
        "type": "hr_copilot.CopilotPendingAction",
        "id": action_id,
        "label": action_type,
    }


def _record_copilot_action_event(
    *, event_type, user, action, request=None, status="SUCCESS", severity="INFO", metadata=None
):
    record_event(
        event_type=event_type,
        category="HR_COPILOT",
        severity=severity,
        status=status,
        actor=user,
        target=_copilot_action_target(
            action.get("action_id", ""), action.get("action_type", action.get("intent", ""))
        ),
        message=f"HR Copilot action {event_type.removeprefix('COPILOT_ACTION_').lower()}.",
        source="HR_COPILOT",
        request=request,
        metadata=metadata or {},
    )


class HRCopilotHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_system_admin or request.user.is_superuser):
            return Response({"detail": "System Admin access is required."}, status=403)
        health = provider_health().as_dict()
        return Response(health, status=200 if health["available"] else 503)


class HRCopilotConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        user = request.user
        if not (user.is_system_admin or user.is_superuser):
            return Response({"detail": "System Admin access is required."}, status=403)
        return Response({
            "conversation_id": conversation_id,
            "messages": load_messages(user, conversation_id),
        })


class HRCopilotQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not (user.is_system_admin or user.is_superuser):
            return Response({"detail": "System Admin access is required."}, status=403)
        question = request.data.get("message", "")
        conversation_id = request.data.get("conversation_id") or str(uuid.uuid4())
        session_id = f"hr-copilot-user-{user.id}"
        
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            return Response({"detail": "Enter a question of up to 2,000 characters."}, status=400)
        if conversation_id is not None and (not isinstance(conversation_id, str) or not conversation_id.strip() or len(conversation_id) > 128):
            return Response({"detail": "conversation_id must be a non-empty string of up to 128 characters."}, status=400)

        audit = CopilotQueryAudit.objects.create(user=user, question=question.strip())
        record_event(
            event_type="COPILOT_CONVERSATION",
            category="HR_COPILOT",
            severity="INFO",
            status="SUCCESS",
            actor=user,
            target=user,
            message="HR Copilot conversation request received.",
            source="HR_COPILOT",
            request=request,
            metadata={"conversation_id": conversation_id, "query_audit_id": audit.id},
        )
        append_message(user, conversation_id, "user", question.strip())
        started_at = time.monotonic()
        intent = None
        scope = None
        try:
            draft = pending_action_manager.get_awaiting_action(session_id, conversation_id, user.id)
            if draft:
                if question.strip().casefold().rstrip('.!') in {'cancel', 'cancel change'}:
                    cancelled = pending_action_manager.cancel_action(session_id, draft['action_id'], user.id)
                    _record_copilot_action_event(
                        event_type="COPILOT_ACTION_CANCELLED",
                        user=user,
                        action=cancelled,
                        request=request,
                    )
                    answer = "Cancelled. No attendance change was made."
                    update_action_message(user, conversation_id, draft['action_id'], 'CANCELLED', answer)
                    append_message(user, conversation_id, 'assistant', answer, {'query_status': 'cancelled'})
                    return Response({'answer': answer, 'intent': cancelled['intent'], 'query_status': 'cancelled', 'conversation_id': conversation_id, 'data': None, 'visualization': None})
                missing = list(draft.get('validation_errors') or [])
                extracted = extract_pending_action_fields(question, missing)
                target_data = dict(draft['target_data'])
                proposed = dict(draft['proposed_changes'])
                for key, value in extracted.items():
                    if key in {'check_in_time', 'check_out_time'}:
                        value = write_action_planner._normalize_time(value, checkout=(key == 'check_out_time'))
                    if value:
                        target_data[key] = value
                        proposed[key] = value
                        if key in missing:
                            missing.remove(key)
                current_state = dict(draft.get('current_state') or {})
                if not target_data.get('employee_id') and (target_data.get('employee_name') or target_data.get('employee_email')):
                    try:
                        employee = write_action_planner._resolve_target_employee(target_data, user, derive_scope(user))
                    except CopilotError as resolution_error:
                        if resolution_error.code == 'employee_ambiguous':
                            missing = ['employee_email'] + [field for field in missing if field not in {'employee_name', 'employee_email'}]
                            description = write_action_planner._missing_question('', missing)
                            updated = pending_action_manager.update_awaiting_action(draft['action_id'], user.id, session_id, {
                                'target_data': target_data, 'proposed_changes': proposed,
                                'validation_errors': missing, 'validated': False,
                                'status': 'AWAITING_INFORMATION', 'description': description,
                            })
                            append_message(user, conversation_id, 'assistant', description, {'query_status': 'awaiting_information', 'pending_action': updated})
                            return Response({'answer': description, 'intent': updated['intent'], 'query_status': 'awaiting_information', 'conversation_id': conversation_id, 'pending_action': updated, 'data': None, 'visualization': None})
                        raise
                    target_data['employee_id'] = employee['employee_id']
                    target_data['employee_name'] = employee['employee_name']
                    missing = [field for field in missing if field not in {'employee_name', 'employee_email'}]
                    if draft['action_type'] == 'leave_create':
                        leave_type = LeaveType.objects.first()
                        if not leave_type:
                            raise CopilotError('no_leave_types', 'No leave types are configured in the system')
                        target_data['leave_type_id'] = leave_type.id
                        proposed['leave_type'] = leave_type.name
                    else:
                        attendance = Attendance.objects.filter(employee_id=employee['employee_id'], date=target_data['date']).first()
                        current_state.update({
                            'exists': attendance is not None,
                            'current_status': attendance.status if attendance else None,
                            'employee_id': employee['employee_id'], 'date': target_data['date'],
                        })
                        proposed['operation'] = 'update' if attendance else 'create'
                if target_data.get('target_status') == 'PRESENT' and not missing:
                    if target_data.get('check_out_time', '') <= target_data.get('check_in_time', ''):
                        raise CopilotError("invalid_attendance_time", "Check-out must be later than check-in.")
                employee_name = target_data.get('employee_name', 'the employee')
                if missing:
                    description = write_action_planner._missing_question(employee_name, missing)
                    status = 'AWAITING_INFORMATION'
                elif draft['action_type'] == 'leave_create':
                    description = f"Confirm {employee_name}'s leave on {target_data['start_date']}: {target_data['reason']}"
                    status = 'PENDING'
                else:
                    description = write_action_planner._attendance_description(
                        employee_name, datetime.fromisoformat(target_data['date']).date(),
                        target_data['target_status'], target_data.get('check_in_time'),
                        target_data.get('check_out_time'), target_data.get('reason'),
                    )
                    status = 'PENDING'
                updated = pending_action_manager.update_awaiting_action(draft['action_id'], user.id, session_id, {
                    'target_data': target_data, 'proposed_changes': proposed, 'current_state': current_state,
                    'validation_errors': missing, 'validated': not missing,
                    'status': status, 'description': description,
                })
                query_status = 'awaiting_information' if missing else 'pending_approval'
                append_message(user, conversation_id, 'assistant', description, {
                    'query_status': query_status, 'pending_action': updated,
                })
                return Response({
                    'answer': description, 'intent': updated['intent'], 'query_status': query_status,
                    'conversation_id': conversation_id, 'action_id': updated['action_id'],
                    'pending_action': updated, 'data': None, 'visualization': None,
                })

            command = question.strip().casefold().rstrip('.!')
            active_actions = pending_action_manager.get_session_actions(session_id, user.id)
            active_action = next((item for item in active_actions.values() if item.get('conversation_id') == conversation_id), None)
            if active_action and command in {'approve', 'approve change', 'confirm', 'yes approve', 'cancel', 'cancel change'}:
                if command.startswith('cancel'):
                    cancelled = pending_action_manager.cancel_action(session_id, active_action['action_id'], user.id)
                    _record_copilot_action_event(
                        event_type="COPILOT_ACTION_CANCELLED",
                        user=user,
                        action=cancelled,
                        request=request,
                    )
                    answer = "Cancelled. No attendance change was made."
                    update_action_message(user, conversation_id, active_action['action_id'], 'CANCELLED', answer)
                    append_message(user, conversation_id, 'assistant', answer, {'query_status': 'cancelled'})
                    return Response({'answer': answer, 'intent': cancelled['intent'], 'query_status': 'cancelled', 'conversation_id': conversation_id, 'data': None, 'visualization': None})
                approved = pending_action_manager.approve_action(session_id, active_action['action_id'], user.id)
                _record_copilot_action_event(
                    event_type="COPILOT_ACTION_CONFIRMED",
                    user=user,
                    action=approved,
                    request=request,
                )
                try:
                    result = write_action_executor.execute_approved_action(approved, user)
                    pending_action_manager.mark_executed(active_action['action_id'], user.id, session_id, result)
                except CopilotError as action_error:
                    pending_action_manager.mark_failed(active_action['action_id'], user.id, session_id, action_error.message)
                    HRCopilotActionApprovalView._record_failure(user, active_action['action_id'], session_id, action_error.message, request)
                    raise
                except Exception as action_error:
                    pending_action_manager.mark_failed(active_action['action_id'], user.id, session_id, 'Action execution failed')
                    HRCopilotActionApprovalView._record_failure(user, active_action['action_id'], session_id, str(action_error), request)
                    raise
                answer = result.get('message', 'The approved change was applied.')
                update_action_message(user, conversation_id, active_action['action_id'], 'EXECUTED', answer)
                append_message(user, conversation_id, 'assistant', answer, {'query_status': 'executed'})
                return Response({'answer': answer, 'intent': approved['intent'], 'query_status': 'executed', 'conversation_id': conversation_id, 'action_result': result, 'data': None, 'visualization': None})

            context = load_context(user, conversation_id)
            intent = analyze_question(question, context, session_id=session_id)
            intent = apply_context(question, intent, context)
            audit.intent = intent
            scope = derive_scope(user)
            
            # Check if this is a write action requiring approval
            if intent.get('action_type') == 'write':
                # Add original query to intent for fallback processing
                intent['original_query'] = question
                
                try:
                    # Plan the write action
                    pending_action = write_action_planner.plan_write_action(intent, user, session_id)
                    pending_action['conversation_id'] = conversation_id
                    
                    # Store the pending action
                    action_id = pending_action_manager.store_pending_action(session_id, pending_action)
                    _record_copilot_action_event(
                        event_type="COPILOT_ACTION_REQUESTED",
                        user=user,
                        action={**pending_action, "action_id": action_id},
                        request=request,
                        metadata={"query_audit_id": audit.id},
                    )
                    
                    # Save conversation context
                    save_context(user, conversation_id, {
                        'pending_action_id': action_id,
                        'last_intent': intent['intent'],
                        'action_type': 'write'
                    })
                    
                    audit.execution_result = "pending_approval"
                    audit.save(update_fields=[
                        "intent", "query_plan", "execution_result"
                    ])
                    
                    # Serialize datetime objects properly for JSON response
                    target_data = pending_action['target_data'].copy()
                    if 'date' in target_data and hasattr(target_data['date'], 'isoformat'):
                        target_data['date'] = target_data['date'].isoformat()
                    elif isinstance(target_data.get('date'), str):
                        # Already a string, keep as-is
                        pass
                    
                    current_state = pending_action['current_state'].copy()
                    if 'date' in current_state and hasattr(current_state['date'], 'isoformat'):
                        current_state['date'] = current_state['date'].isoformat()

                    query_status = "awaiting_information" if pending_action.get('status') == 'AWAITING_INFORMATION' else "pending_approval"
                    append_message(user, conversation_id, "assistant", pending_action['description'], {
                        "query_status": query_status,
                        "pending_action": {**pending_action, "action_id": action_id},
                    })
                    
                    return Response({
                        "answer": pending_action['description'],
                        "intent": intent["intent"],
                        "scope": {"sections": scope["sections"], "subsections": scope["subsections"]},
                        "query_status": query_status,
                        "conversation_id": conversation_id,
                        "action_id": action_id,
                        "pending_action": {
                            "action_id": action_id,
                            "action_type": pending_action['action_type'],
                            "status": pending_action.get('status', 'PENDING'),
                            "validation_errors": pending_action.get('validation_errors') or [],
                            "description": pending_action['description'],
                            "warning_message": pending_action.get('warning_message'),
                            "target_data": target_data,
                            "proposed_changes": pending_action['proposed_changes'],
                            "current_state": current_state,
                            "expires_at": pending_action['expires_at'].isoformat() if pending_action.get('expires_at') else None
                        },
                        "data": None,
                        "visualization": None,
                    })
                    
                except CopilotError as write_error:
                    if write_error.code == 'employee_ambiguous':
                        entities = intent.get('entities', {})
                        draft_intent = {**intent, 'entities': {key: value for key, value in entities.items() if key not in {'employee_name', 'employee_email', 'employee_id'}}}
                        pending_action = write_action_planner._plan_missing_employee(draft_intent, user, scope, session_id)
                        pending_action['target_data']['employee_name'] = entities.get('employee_name')
                        pending_action['validation_errors'] = ['employee_email'] + [
                            field for field in pending_action['validation_errors'] if field != 'employee_name'
                        ]
                        pending_action['description'] = write_action_planner._missing_question('', pending_action['validation_errors'])
                        pending_action['conversation_id'] = conversation_id
                        action_id = pending_action_manager.store_pending_action(session_id, pending_action)
                        _record_copilot_action_event(
                            event_type="COPILOT_ACTION_REQUESTED",
                            user=user,
                            action={**pending_action, "action_id": action_id},
                            request=request,
                            metadata={"query_audit_id": audit.id},
                        )
                        append_message(user, conversation_id, 'assistant', pending_action['description'], {
                            'query_status': 'awaiting_information',
                            'pending_action': {**pending_action, 'action_id': action_id},
                        })
                        audit.intent = intent
                        audit.execution_result = 'awaiting_information'
                        audit.save(update_fields=['intent', 'execution_result'])
                        return Response({
                            'answer': pending_action['description'], 'intent': intent['intent'],
                            'query_status': 'awaiting_information', 'conversation_id': conversation_id,
                            'action_id': action_id,
                            'pending_action': {
                                'action_id': action_id, 'action_type': pending_action['action_type'],
                                'status': 'AWAITING_INFORMATION', 'description': pending_action['description'],
                                'target_data': pending_action['target_data'],
                                'proposed_changes': pending_action['proposed_changes'],
                                'validation_errors': pending_action['validation_errors'],
                            },
                            'data': None, 'visualization': None,
                        })
                    raise
                except Exception as write_error:
                    logger.exception("Write action could not be planned; audit_id=%s", audit.pk)
                    raise CopilotError(
                        "write_action_failed",
                        "I couldn't safely prepare that change. Please provide the employee, date, and requested change clearly.",
                        400,
                    ) from write_error
            
            # Handle read operations (existing logic)
            plan = plan_query(intent, scope)
            audit.query_plan = plan
            sql, data, columns = "", [], []
            if plan["source"] == "employee" and plan["intent"] == "employee_lookup" and plan["employee"]["status"] == "resolved":
                data = hr_tools.get_employee_profile(employee_id=plan["employee"]["employee_id"], scope=scope)
                columns = list(data[0]) if data else []
                audit.sql = ""
            else:
                sql, data, columns = hr_tools.execute_plan(
                    plan, execute_query_fn=execute_query, validate_sql_fn=validate_sql,
                )
                audit.sql = sql
            audit.validation_result = "passed"
            audit.scope_result = "passed"
            answer = generate_natural_answer(question, intent, data, session_id=session_id) or generate_answer(intent, data) or "Here are your requested HR records."
            save_context(user, conversation_id, plan)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "HR Copilot trace question=%r intent=%s entities=%s employee=%s temporal=%s plan=%s scope=%s sql=%s params=%s result_count=%d elapsed_ms=%.2f response_type=%s",
                    question.strip(), intent.get("intent"), intent.get("entities"), plan.get("employee"),
                    plan.get("temporal_scope"), plan, scope, sql, [], len(data),
                    (time.monotonic() - started_at) * 1000, "answer",
                )
            audit.execution_result = "success"
            audit.save(update_fields=[
                "intent", "query_plan", "sql", "validation_result", "scope_result",
                "execution_result",
            ])
            append_message(user, conversation_id, "assistant", answer, {
                "query_status": "executed",
                "data": {"columns": columns, "rows": data, "row_count": len(data)},
            })
            return Response({
                "answer": answer,
                "intent": intent["intent"],
                "scope": {"sections": scope["sections"], "subsections": scope["subsections"]},
                "query_status": "executed",
                "conversation_id": conversation_id,
                "data": {"columns": columns, "rows": data, "row_count": len(data)},
                "visualization": None,
            })
        except CopilotError as error:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "HR Copilot trace question=%r intent=%s entities=%s temporal=%s scope=%s result_count=0 elapsed_ms=%.2f response_type=%s code=%s",
                    question.strip(), intent.get("intent") if intent else "unknown",
                    intent.get("entities") if intent else {}, intent.get("entities", {}).get("temporal_scope") if intent else None,
                    scope, (time.monotonic() - started_at) * 1000, "clarification_or_rejection", error.code,
                )
            audit.intent = intent or {}
            audit.scope_result = "denied" if error.status == 403 else ("passed" if scope else "not_run")
            audit.validation_result = "rejected" if error.code == "sql_rejected" else audit.validation_result
            audit.execution_result = "rejected"
            audit.error_code = error.code
            audit.save(update_fields=[
                "intent", "scope_result", "validation_result", "execution_result", "error_code",
            ])
            record_event(
                event_type="COPILOT_QUERY_FAILED",
                category="HR_COPILOT",
                severity="WARNING" if error.status < 500 else "ERROR",
                status="FAILED",
                actor=user,
                target=user,
                message="HR Copilot query failed.",
                source="HR_COPILOT",
                request=request,
                metadata={"query_audit_id": audit.id, "error_code": error.code},
            )
            append_message(user, conversation_id, "assistant", error.message, {"query_status": "rejected"})
            return Response({
                "detail": error.message,
                "answer": error.message,
                "intent": intent["intent"] if intent else "unknown",
                "scope": {"sections": scope["sections"], "subsections": scope["subsections"]} if scope else None,
                "query_status": "rejected",
                "conversation_id": conversation_id,
                "data": None,
                "visualization": None,
                "code": error.code,
            }, status=error.status)
        except Exception as e:
            logger.exception("HR Copilot query failed; audit_id=%s; error=%s", audit.pk, str(e))
            audit.intent = intent or {}
            audit.scope_result = "passed" if scope else "not_run"
            audit.execution_result = "failed"
            audit.error_code = "query_failed"
            audit.save(update_fields=["intent", "scope_result", "execution_result", "error_code"])
            record_event(
                event_type="COPILOT_QUERY_FAILED",
                category="HR_COPILOT",
                severity="ERROR",
                status="FAILED",
                actor=user,
                target=user,
                message="HR Copilot query failed.",
                source="HR_COPILOT",
                request=request,
                metadata={"query_audit_id": audit.id, "error_code": "query_failed"},
            )
            append_message(user, conversation_id, "assistant", "I couldn't complete that HR query. Please try a more specific question.", {"query_status": "failed"})
            return Response({
                "detail": "I couldn't complete that HR query. Please try a more specific question.",
                "answer": "I couldn't complete that HR query. Please try a more specific question.",
                "intent": intent["intent"] if intent else "unknown",
                "scope": {"sections": scope["sections"], "subsections": scope["subsections"]} if scope else None,
                "query_status": "failed",
                "conversation_id": conversation_id,
                "data": None,
                "visualization": None,
                "code": "query_failed",
            }, status=503)


class HRCopilotActionApprovalView(APIView):
    """Handle approval/cancellation of pending write actions."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not (user.is_system_admin or user.is_superuser):
            return Response({"detail": "System Admin access is required."}, status=403)
        
        action_id = request.data.get("action_id")
        action = request.data.get("action")  # "approve" or "cancel"
        session_id = f"hr-copilot-user-{user.id}"
        
        if not action_id or not action:
            return Response({"detail": "action_id and action are required."}, status=400)
        
        if action not in ["approve", "cancel"]:
            return Response({"detail": "action must be 'approve' or 'cancel'."}, status=400)
        
        try:
            if action == "approve":
                # Get and approve the pending action
                pending_action = pending_action_manager.approve_action(session_id, action_id, user.id)
                _record_copilot_action_event(
                    event_type="COPILOT_ACTION_CONFIRMED",
                    user=user,
                    action=pending_action,
                    request=request,
                )
                
                # Execute the approved action
                result = write_action_executor.execute_approved_action(pending_action, user)
                pending_action_manager.mark_executed(action_id, user.id, session_id, result)
                answer = result.get('message') or f"{pending_action['intent'].replace('_', ' ').title()} completed successfully."
                conversation_id = pending_action.get('conversation_id')
                update_action_message(user, conversation_id, action_id, 'EXECUTED', answer)
                append_message(user, conversation_id, "assistant", answer, {"query_status": "executed"})
                
                # Generate natural language response
                from .services.llm import generate_natural_answer
                natural_response = generate_natural_answer(
                    f"Action completed: {pending_action['description']}", 
                    {'intent': pending_action['intent']}, 
                    [result],
                    session_id=session_id
                )
                
                return Response({
                    "answer": answer,
                    "intent": pending_action['intent'],
                    "query_status": "executed",
                    "action_result": result,
                    "data": None,
                    "visualization": None,
                })
                
            else:  # cancel
                cancelled_action = pending_action_manager.cancel_action(session_id, action_id, user.id)
                _record_copilot_action_event(
                    event_type="COPILOT_ACTION_CANCELLED",
                    user=user,
                    action=cancelled_action,
                    request=request,
                )
                conversation_id = cancelled_action.get('conversation_id')
                answer = "Cancelled. No attendance change was made."
                update_action_message(user, conversation_id, action_id, 'CANCELLED', answer)
                append_message(user, conversation_id, "assistant", answer, {"query_status": "cancelled"})
                return Response({
                    "answer": answer,
                    "intent": cancelled_action['intent'],
                    "query_status": "cancelled",
                    "data": None,
                    "visualization": None,
                })
                
        except CopilotError as error:
            if action == "approve" and action_id:
                pending_action_manager.mark_failed(action_id, user.id, session_id, error.message)
                self._record_failure(user, action_id, session_id, error.message, request)
            return Response({
                "detail": error.message,
                "answer": error.message,
                "query_status": "failed",
                "code": error.code,
            }, status=error.status)
        except Exception as e:
            logger.exception(f"Action {action} failed for {action_id}")
            if action == "approve" and action_id:
                pending_action_manager.mark_failed(action_id, user.id, session_id, "Action execution failed")
                self._record_failure(user, action_id, session_id, "Action execution failed", request)
            return Response({
                "detail": "The requested action could not be completed. No success was recorded.",
                "answer": "The requested action could not be completed. No success was recorded.",
                "query_status": "failed",
                "code": "action_failed",
            }, status=500)

    @staticmethod
    def _record_failure(user, action_id, session_id, message, request):
        try:
            pending = CopilotPendingAction.objects.get(action_id=action_id, user=user, session_id=session_id)
            CopilotActionAudit.objects.create(
                pending_action=pending, user=user, session_id=session_id,
                action_type='write', intent=pending.intent, operation=pending.action_type,
                target_description=pending.description, previous_state=pending.current_state or {},
                new_state=None, success=False, explicit_confirmation=bool(pending.approved_at),
                error_message=message[:2000], authorization_scope=pending.authorization_scope or {},
                ip_address=HRCopilotActionApprovalView._client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
            )
            _record_copilot_action_event(
                event_type="COPILOT_ACTION_FAILED",
                user=user,
                action={
                    "action_id": action_id,
                    "action_type": pending.action_type,
                },
                request=request,
                status="FAILED",
                severity="ERROR",
                metadata={"action_audit_id": pending.audit_records.order_by("-timestamp").first().id},
            )
        except Exception:
            logger.exception("Could not persist failed Copilot action audit for %s", action_id)

    @staticmethod
    def _client_ip(request):
        value = request.META.get('REMOTE_ADDR')
        return value if value and len(value) <= 45 else None


class HRCopilotPendingActionsView(APIView):
    """List pending actions for the current session."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not (user.is_system_admin or user.is_superuser):
            return Response({"detail": "System Admin access is required."}, status=403)
        
        session_id = f"hr-copilot-user-{user.id}"
        
        try:
            pending_actions = pending_action_manager.get_session_actions(session_id, user.id)
            
            # Filter to only pending actions and format for frontend
            active_actions = []
            for action_id, action in pending_actions.items():
                if action['status'] == 'PENDING':
                    active_actions.append({
                        "action_id": action_id,
                        "description": action['description'],
                        "warning_message": action.get('warning_message'),
                        "target_data": action['target_data'],
                        "proposed_changes": action['proposed_changes'],
                        "current_state": action['current_state'],
                        "intent": action['intent'],
                        "expires_at": action['expires_at'],
                        "created_at": action['created_at']
                    })
            
            return Response({
                "pending_actions": active_actions,
                "count": len(active_actions)
            })
            
        except Exception as e:
            logger.exception("Failed to get pending actions")
            return Response({
                "detail": f"Failed to get pending actions: {str(e)}",
                "pending_actions": [],
                "count": 0
            }, status=500)
