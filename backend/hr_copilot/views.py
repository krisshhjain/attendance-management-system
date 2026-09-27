import logging
import time

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CopilotQueryAudit
from .services.conversation import apply_context, load_context, save_context
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

logger = logging.getLogger(__name__)


class HRCopilotHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_system_admin or request.user.is_superuser):
            return Response({"detail": "System Admin access is required."}, status=403)
        health = provider_health().as_dict()
        return Response(health, status=200 if health["available"] else 503)


class HRCopilotQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not (user.is_system_admin or user.is_superuser):
            return Response({"detail": "System Admin access is required."}, status=403)
        question = request.data.get("message", "")
        conversation_id = request.data.get("conversation_id")
        session_id = request.session.session_key or f"session_{user.id}_{int(time.time())}"
        
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            return Response({"detail": "Enter a question of up to 2,000 characters."}, status=400)
        if conversation_id is not None and (not isinstance(conversation_id, str) or not conversation_id.strip() or len(conversation_id) > 128):
            return Response({"detail": "conversation_id must be a non-empty string of up to 128 characters."}, status=400)

        audit = CopilotQueryAudit.objects.create(user=user, question=question.strip())
        started_at = time.monotonic()
        intent = None
        scope = None
        try:
            context = load_context(user, conversation_id)
            intent = analyze_question(question, context, session_id=session_id)
            intent = apply_context(question, intent, context)
            audit.intent = intent
            scope = derive_scope(user)
            
            # Check if this is a write action requiring approval
            if intent.get('action_type') == 'write' and intent.get('requires_approval'):
                # Add original query to intent for fallback processing
                intent['original_query'] = question
                
                try:
                    # Plan the write action
                    pending_action = write_action_planner.plan_write_action(intent, user, session_id)
                    
                    # Store the pending action
                    action_id = pending_action_manager.store_pending_action(session_id, pending_action)
                    
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
                    
                    return Response({
                        "answer": pending_action['description'],
                        "intent": intent["intent"],
                        "scope": {"sections": scope["sections"], "subsections": scope["subsections"]},
                        "query_status": "pending_approval",
                        "action_id": action_id,
                        "pending_action": {
                            "action_id": action_id,
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
                    
                except Exception as write_error:
                    logger.exception("Write action failed; falling back to read operation; error=%s", write_error)
                    # If write action fails, fall through to read operations as fallback
                    pass
            
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
            return Response({
                "answer": answer,
                "intent": intent["intent"],
                "scope": {"sections": scope["sections"], "subsections": scope["subsections"]},
                "query_status": "executed",
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
            return Response({
                "detail": error.message,
                "answer": error.message,
                "intent": intent["intent"] if intent else "unknown",
                "scope": {"sections": scope["sections"], "subsections": scope["subsections"]} if scope else None,
                "query_status": "rejected",
                "data": None,
                "visualization": None,
                "code": error.code,
            }, status=error.status)
        except Exception as e:
            logger.exception("HR Copilot query failed; audit_id=%s; error=%s", audit.pk, str(e))
            print(f"DEBUG: HR Copilot exception: {type(e).__name__}: {e}")  # Temporary debug
            audit.intent = intent or {}
            audit.scope_result = "passed" if scope else "not_run"
            audit.execution_result = "failed"
            audit.error_code = "query_failed"
            audit.save(update_fields=["intent", "scope_result", "execution_result", "error_code"])
            return Response({
                "detail": "I couldn't complete that HR query. Please try a more specific question.",
                "answer": "I couldn't complete that HR query. Please try a more specific question.",
                "intent": intent["intent"] if intent else "unknown",
                "scope": {"sections": scope["sections"], "subsections": scope["subsections"]} if scope else None,
                "query_status": "failed",
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
        session_id = request.session.session_key or f"session_{user.id}_{int(time.time())}"
        
        if not action_id or not action:
            return Response({"detail": "action_id and action are required."}, status=400)
        
        if action not in ["approve", "cancel"]:
            return Response({"detail": "action must be 'approve' or 'cancel'."}, status=400)
        
        try:
            if action == "approve":
                # Get and approve the pending action
                pending_action = pending_action_manager.approve_action(session_id, action_id)
                
                # Execute the approved action
                result = write_action_executor.execute_approved_action(pending_action, user)
                
                # Generate natural language response
                from .services.llm import generate_natural_answer
                natural_response = generate_natural_answer(
                    f"Action completed: {pending_action['description']}", 
                    {'intent': pending_action['intent']}, 
                    [result],
                    session_id=session_id
                )
                
                return Response({
                    "answer": natural_response or result['message'],
                    "intent": pending_action['intent'],
                    "query_status": "executed",
                    "action_result": result,
                    "data": None,
                    "visualization": None,
                })
                
            else:  # cancel
                cancelled_action = pending_action_manager.cancel_action(session_id, action_id)
                
                return Response({
                    "answer": f"Action cancelled: {cancelled_action['description']}",
                    "intent": cancelled_action['intent'],
                    "query_status": "cancelled",
                    "data": None,
                    "visualization": None,
                })
                
        except CopilotError as error:
            return Response({
                "detail": error.message,
                "answer": error.message,
                "query_status": "failed",
                "code": error.code,
            }, status=error.status)
        except Exception as e:
            logger.exception(f"Action {action} failed for {action_id}")
            return Response({
                "detail": f"Action {action} failed: {str(e)}",
                "answer": f"Action {action} failed: {str(e)}",
                "query_status": "failed",
                "code": "action_failed",
            }, status=500)


class HRCopilotPendingActionsView(APIView):
    """List pending actions for the current session."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not (user.is_system_admin or user.is_superuser):
            return Response({"detail": "System Admin access is required."}, status=403)
        
        session_id = request.session.session_key or f"session_{user.id}_{int(time.time())}"
        
        try:
            pending_actions = pending_action_manager.get_session_actions(session_id)
            
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
