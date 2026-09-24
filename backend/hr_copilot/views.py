import logging
import time

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CopilotQueryAudit
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

logger = logging.getLogger(__name__)


class HRCopilotQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not (user.is_system_admin or user.is_superuser):
            return Response({"detail": "System Admin access is required."}, status=403)
        question = request.data.get("message", "")
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            return Response({"detail": "Enter a question of up to 2,000 characters."}, status=400)

        audit = CopilotQueryAudit.objects.create(user=user, question=question.strip())
        started_at = time.monotonic()
        intent = None
        scope = None
        try:
            intent = analyze_question(question)
            audit.intent = intent
            scope = derive_scope(user)
            plan = plan_query(intent, scope)
            audit.query_plan = plan
            sql, params = build_sql(plan)
            validate_sql(sql, plan)
            audit.sql = sql
            audit.validation_result = "passed"
            audit.scope_result = "passed"
            columns, rows = execute_query(sql, params)
            data = serialize_result(columns, rows)
            answer = generate_answer(intent, data)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "HR Copilot trace question=%r intent=%s entities=%s employee=%s temporal=%s plan=%s scope=%s sql=%s params=%s result_count=%d elapsed_ms=%.2f response_type=%s",
                    question.strip(), intent.get("intent"), intent.get("entities"), plan.get("employee"),
                    plan.get("temporal_scope"), plan, scope, sql, params, len(data),
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
        except Exception:
            logger.exception("HR Copilot query failed; audit_id=%s", audit.pk)
            audit.intent = intent or {}
            audit.scope_result = "passed" if scope else "not_run"
            audit.execution_result = "failed"
            audit.error_code = "query_failed"
            audit.save(update_fields=["intent", "scope_result", "execution_result", "error_code"])
            return Response({
                "detail": "I couldn’t complete that HR query. Please try a more specific question.",
                "answer": "I couldn’t complete that HR query. Please try a more specific question.",
                "intent": intent["intent"] if intent else "unknown",
                "scope": {"sections": scope["sections"], "subsections": scope["subsections"]} if scope else None,
                "query_status": "failed",
                "data": None,
                "visualization": None,
                "code": "query_failed",
            }, status=503)
