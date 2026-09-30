"""Typed, read-only leave and regularization tools for HR Copilot."""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from attendance.models import AttendanceCorrection, AttendanceEvent, RegularizationRequest
from employees.models import Employee
from leave_management.models import LeavePolicy, LeaveRequest, LeaveType
from leave_management.services import calculate_employee_leave_balances, get_active_policy

from .pipeline import CopilotError


METRICS = {
    "leave_balance", "leave_requests", "leave_history", "leave_summary", "leave_usage",
    "regularization_history", "regularization_pending", "regularization_summary",
    "attendance_correction_explanation", "leave_policy",
}


def _name(employee):
    return employee.user.get_full_name().strip() or employee.user.email


def _date_range(filters, default_year=False):
    value = filters.get("date_range")
    if value:
        try:
            start, end = date.fromisoformat(value["start"]), date.fromisoformat(value["end"])
        except (KeyError, TypeError, ValueError) as error:
            raise CopilotError("invalid_date_range", "Please provide a valid date range.") from error
        if start > end:
            raise CopilotError("invalid_date_range", "The start date must be on or before the end date.")
        return start, end
    today = timezone.localdate()
    return (date(today.year, 1, 1), date(today.year, 12, 31)) if default_year else (None, None)


class LeaveRegularizationIntelligence:
    def _employees(self, scope, employee_id=None):
        qs = Employee.objects.select_related("user").filter(is_active=True, user__is_active=True)
        if not scope["unrestricted"]:
            qs = qs.filter(section__in=scope["sections"])
            if scope["subsections"]:
                qs = qs.filter(subsection__in=scope["subsections"])
        if employee_id:
            employee = qs.filter(pk=employee_id).first()
            if not employee:
                raise CopilotError("scope_denied", "You do not have access to that employee.", 403)
            return [employee]
        return list(qs.order_by("user__last_name", "user__first_name"))

    @staticmethod
    def _request_row(req):
        return {
            "id": req.id, "employee_id": req.employee_id, "employee_name": _name(req.employee),
            "employee_email": req.employee.user.email, "leave_type": req.leave_type.name,
            "leave_type_code": req.leave_type.code, "start_date": req.start_date.isoformat(),
            "end_date": req.end_date.isoformat(), "duration_days": float(req.duration_days),
            "day_type": req.day_type, "status": req.status, "reason": req.reason,
        }

    @staticmethod
    def _regularization_row(req):
        return {
            "id": req.id, "employee_id": req.employee_id, "employee_name": _name(req.employee),
            "employee_email": req.employee.user.email, "attendance_date": req.attendance_date.isoformat(),
            "request_type": req.request_type, "status": req.status,
            "requested_check_in": req.requested_check_in.isoformat() if req.requested_check_in else None,
            "requested_check_out": req.requested_check_out.isoformat() if req.requested_check_out else None,
            "approved_check_in": req.approved_check_in.isoformat() if req.approved_check_in else None,
            "approved_check_out": req.approved_check_out.isoformat() if req.approved_check_out else None,
            "reason": req.reason, "rejection_reason": req.rejection_reason,
            "attendance_correction_id": req.attendance_correction_id,
        }

    def execute(self, *, metric, scope, user, filters, employee_id=None):
        if metric not in METRICS:
            raise CopilotError("invalid_intelligence_metric", "That leave or regularization query is not supported.")
        employees = self._employees(scope, employee_id)
        if metric == "leave_balance":
            if not employee_id:
                employee = getattr(user, "employee", None)
                employees = self._employees(scope, getattr(employee, "id", None)) if employee else []
                if not employees:
                    raise CopilotError("employee_required", "Please specify an employee for the leave balance.")
            year = int(filters.get("year") or timezone.localdate().year)
            rows = []
            for employee in employees:
                for balance in calculate_employee_leave_balances(employee, year=year):
                    rows.append({"employee_id": employee.id, "employee_name": _name(employee), "year": year, **balance})
            return self._result(metric, {"start": f"{year}-01-01", "end": f"{year}-12-31"}, rows,
                                "Balance uses the application's active leave policy, approved usage, pending usage, and carry-forward rules.")
        if metric == "leave_policy":
            rows = []
            types = LeaveType.objects.filter(is_active=True).order_by("name")
            for leave_type in types:
                targets = employees or [None]
                for employee in targets:
                    policy = get_active_policy(employee, leave_type) if employee else None
                    rows.append({"leave_type_id": leave_type.id, "leave_type": leave_type.name, "code": leave_type.code,
                                 "description": leave_type.description, "is_paid": leave_type.is_paid,
                                 "allow_half_day": policy.allow_half_day if policy else leave_type.allow_half_day,
                                 "requires_document": policy.requires_document if policy else leave_type.requires_document,
                                 "min_notice_days": policy.min_notice_days if policy else leave_type.min_notice_days,
                                 "employee_type": employee.employment_type if employee else None,
                                 "annual_entitlement": float(policy.annual_entitlement) if policy else None})
            return self._result(metric, None, rows, "Policies are effective policies for the requested employee scope; type defaults are shown when no employee was specified.")
        start, end = _date_range(filters, default_year=metric in {"leave_history", "leave_summary", "regularization_history", "regularization_summary"})
        employee_ids = [e.id for e in employees]
        if metric in {"leave_requests", "leave_summary", "leave_usage"}:
            qs = LeaveRequest.objects.select_related("employee__user", "leave_type").filter(employee_id__in=employee_ids)
            status = filters.get("leave_status")
            if status:
                qs = qs.filter(status=status)
            if filters.get("request_id"):
                qs = qs.filter(pk=filters["request_id"])
            if metric == "leave_requests":
                qs = qs.filter(status="PENDING") if not status else qs
            if start and end:
                qs = qs.filter(start_date__lte=end, end_date__gte=start)
            requests = list(qs.order_by("start_date", "id"))
            if metric == "leave_summary":
                counts = Counter(req.status for req in requests)
                rows = [{"status": status, "request_count": count,
                         "duration_days": float(sum((req.duration_days for req in requests if req.status == status), Decimal("0")))}
                        for status, count in sorted(counts.items())]
            elif metric == "leave_usage":
                approved = [req for req in requests if req.status == "APPROVED"]
                grouped = {}
                for req in approved:
                    key = (req.leave_type.name, req.leave_type.code)
                    grouped.setdefault(key, Decimal("0")); grouped[key] += req.duration_days
                rows = [{"leave_type": k[0], "leave_type_code": k[1], "used_days": float(v)} for k, v in grouped.items()]
            else:
                rows = [self._request_row(req) for req in requests]
            return self._result(metric, _range_json(start, end), rows, "Leave request duration uses the stored duration calculated by the leave-management service.")
        rq = RegularizationRequest.objects.select_related("employee__user", "attendance_correction").filter(employee_id__in=employee_ids)
        if filters.get("regularization_status"):
            rq = rq.filter(status=filters["regularization_status"])
        if metric == "regularization_pending":
            rq = rq.filter(status="PENDING")
        if start and end:
            rq = rq.filter(attendance_date__range=(start, end))
        if metric == "attendance_correction_explanation":
            if filters.get("request_id"):
                rq = rq.filter(pk=filters["request_id"])
            matches = list(rq.order_by("-created_at"))
            if len(matches) > 1:
                raise CopilotError("request_ambiguous", "More than one regularization matched. Please provide the request ID.")
            if not matches:
                raise CopilotError("request_not_found", "No matching regularization or attendance correction was found.")
            req = matches[0]
            events = AttendanceEvent.objects.filter(correction_id=req.attendance_correction_id).order_by("timestamp", "id") if req.attendance_correction_id else []
            row = self._regularization_row(req)
            row["corrective_events"] = [{"event_type": e.event_type, "timestamp": e.timestamp.isoformat(), "source": e.source} for e in events]
            row["explanation"] = "The approved regularization is linked to the corrective attendance events listed here; historical events remain auditable."
            return self._result(metric, _range_json(start, end), [row], "Explanation is based on the regularization request, linked correction, and correction-linked events.")
        requests = list(rq.order_by("attendance_date", "id"))
        if metric == "regularization_summary":
            counts = Counter(req.status for req in requests)
            rows = [{"status": status, "request_count": count} for status, count in sorted(counts.items())]
        else:
            rows = [self._regularization_row(req) for req in requests]
        return self._result(metric, _range_json(start, end), rows, "Regularization results are read from the application's request and correction records.")

    @staticmethod
    def _result(metric, date_range, rows, assumption):
        return {"metric": metric, "date_range": date_range, "assumptions": [assumption], "rows": rows}


def _range_json(start, end):
    return {"start": start.isoformat(), "end": end.isoformat()} if start and end else None


leave_regularization_intelligence = LeaveRegularizationIntelligence()
