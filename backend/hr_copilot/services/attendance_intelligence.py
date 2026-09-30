"""Read-only attendance intelligence built on the attendance domain rules."""

from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from attendance.models import (
    Attendance,
    AttendanceEvent,
    calculate_completed_working_duration,
    get_effective_attendance_events,
)
from config.business_rules import is_working_day
from employees.models import Employee
from leave_management.models import LeaveRequest

from .pipeline import CopilotError


METRICS = {
    "missing_checkins",
    "late_employees",
    "working_hours",
    "incomplete_explanation",
    "absence_streaks",
    "summary",
    "period_comparison",
}


def _date_range(start, end):
    return {"start": start.isoformat(), "end": end.isoformat()}


def _parse_range(value):
    try:
        start = date.fromisoformat(value["start"])
        end = date.fromisoformat(value["end"])
    except (KeyError, TypeError, ValueError) as error:
        raise CopilotError("invalid_date_range", "Please provide a valid attendance date range.") from error
    if start > end:
        raise CopilotError("invalid_date_range", "The attendance range must start before it ends.")
    return start, end


class AttendanceIntelligence:
    """Typed, scope-aware attendance read tools."""

    @staticmethod
    def _employees(scope, target_employee_id=None, target_date=None):
        employees = Employee.objects.select_related("user", "shift").filter(
            is_active=True,
            user__is_active=True,
        )
        if target_date:
            employees = employees.filter(date_joined__lte=target_date)
        if target_employee_id:
            employees = employees.filter(pk=target_employee_id)
        if not scope["unrestricted"]:
            employees = employees.filter(section__in=scope["sections"])
            if scope["subsections"]:
                employees = employees.filter(subsection__in=scope["subsections"])
        return employees.order_by("user__last_name", "user__first_name")

    @staticmethod
    def _employee_name(employee):
        return employee.user.get_full_name().strip() or employee.user.email

    @staticmethod
    def _approved_leave(employee, target_date):
        return LeaveRequest.objects.filter(
            employee=employee,
            status="APPROVED",
            start_date__lte=target_date,
            end_date__gte=target_date,
        ).first()

    @staticmethod
    def _events(employee, target_date):
        return list(get_effective_attendance_events(employee, target_date))

    def _state(self, employee, target_date):
        events = self._events(employee, target_date)
        attendance = Attendance.objects.filter(employee=employee, date=target_date).first()
        leave = self._approved_leave(employee, target_date)
        last_event = events[-1] if events else None
        if leave or (attendance and attendance.status == "LEAVE"):
            status = "LEAVE"
        elif last_event and last_event.event_type == "CHECK_IN":
            status = "INCOMPLETE"
        elif last_event and last_event.event_type == "CHECK_OUT":
            status = "PRESENT"
        elif attendance and attendance.status in {"ABSENT", "INCOMPLETE", "PRESENT"}:
            status = attendance.status
        else:
            status = "ABSENT"
        return {
            "status": status,
            "events": events,
            "attendance": attendance,
            "leave": leave,
        }

    def _base(self, metric, start, end, assumptions, rows):
        return {
            "metric": metric,
            "date_range": _date_range(start, end),
            "assumptions": assumptions,
            "rows": rows,
        }

    def missing_checkins(self, *, scope, target_date, target_employee_id=None):
        if not is_working_day(target_date):
            return self._base(
                "missing_checkins", target_date, target_date,
                ["Weekly holidays are excluded from missing-check-in detection."], [],
            )
        rows = []
        for employee in self._employees(scope, target_employee_id, target_date):
            state = self._state(employee, target_date)
            if state["leave"] or state["status"] == "LEAVE":
                continue
            if not any(event.event_type == "CHECK_IN" for event in state["events"]):
                rows.append({
                    "employee_id": employee.id,
                    "employee_name": self._employee_name(employee),
                    "email": employee.user.email,
                    "section": employee.section,
                    "subsection": employee.subsection,
                })
        return self._base(
            "missing_checkins", target_date, target_date,
            ["Active employees who had joined by the date are considered.", "A check-in in the effective event set counts as checked in."],
            rows,
        )

    def late_employees(self, *, scope, target_date, target_employee_id=None):
        rows = []
        for employee in self._employees(scope, target_employee_id, target_date):
            state = self._state(employee, target_date)
            attendance = state["attendance"]
            if not attendance or not attendance.check_in:
                continue
            # Reuse the existing domain adherence rule, including its five
            # minute grace period and assigned-shift semantics.
            if attendance.get_shift_adherence() == "LATE":
                rows.append({
                    "employee_id": employee.id,
                    "employee_name": self._employee_name(employee),
                    "email": employee.user.email,
                    "check_in": attendance.check_in.isoformat(),
                    "shift": employee.shift.name if employee.shift else None,
                })
        return self._base(
            "late_employees", target_date, target_date,
            ["Late means the existing Attendance shift-adherence rule returned LATE.", "Employees without a check-in or assigned shift are not listed as late."],
            rows,
        )

    def working_hours(self, *, scope, start, end, user, target_employee_id=None):
        employee_id = target_employee_id
        if employee_id is None:
            employee_id = getattr(getattr(user, "employee", None), "id", None)
        if employee_id is None:
            raise CopilotError("employee_required", "Specify an employee or use an account linked to an employee profile.")
        employees = list(self._employees(scope, employee_id))
        if not employees:
            raise CopilotError("scope_denied", "You do not have access to that employee.", 403)
        employee = employees[0]
        total = timedelta(0)
        daily = []
        current = start
        while current <= end:
            state = self._state(employee, current)
            duration = calculate_completed_working_duration(state["events"])
            total += duration
            daily.append({
                "date": current.isoformat(),
                "status": state["status"],
                "working_duration_seconds": int(duration.total_seconds()),
                "working_duration": str(duration),
            })
            current += timedelta(days=1)
        return self._base(
            "working_hours", start, end,
            ["Only closed effective CHECK_IN/CHECK_OUT intervals are summed.", "Open intervals and weekly holidays are reported but do not add completed hours."],
            [{
                "employee_id": employee.id,
                "employee_name": self._employee_name(employee),
                "email": employee.user.email,
                "total_working_seconds": int(total.total_seconds()),
                "total_working_duration": str(total),
                "daily": daily,
            }],
        )

    def incomplete_explanation(self, *, scope, target_date, user, target_employee_id=None):
        employee_id = target_employee_id or getattr(getattr(user, "employee", None), "id", None)
        if employee_id is None:
            raise CopilotError("employee_required", "Specify an employee or use an account linked to an employee profile.")
        employees = list(self._employees(scope, employee_id, target_date))
        if not employees:
            raise CopilotError("scope_denied", "You do not have access to that employee.", 403)
        employee = employees[0]
        state = self._state(employee, target_date)
        events = state["events"]
        if state["status"] != "INCOMPLETE":
            explanation = f"Attendance is {state['status'].lower()} for this date, not incomplete."
        elif events and events[-1].event_type == "CHECK_IN":
            explanation = "The effective attendance events contain a check-in without a following check-out."
        else:
            explanation = "The attendance record is marked incomplete and needs review."
        return self._base(
            "incomplete_explanation", target_date, target_date,
            ["The explanation uses effective attendance events, approved leave, and the persisted attendance status."],
            [{
                "employee_id": employee.id,
                "employee_name": self._employee_name(employee),
                "date": target_date.isoformat(),
                "status": state["status"],
                "explanation": explanation,
                "check_in": events[0].timestamp.isoformat() if events and events[0].event_type == "CHECK_IN" else None,
                "check_out": next((event.timestamp.isoformat() for event in reversed(events) if event.event_type == "CHECK_OUT"), None),
                "needs_regularization": state["status"] == "INCOMPLETE",
            }],
        )

    def _absence_dates(self, start, end):
        current = start
        values = []
        while current <= end:
            if is_working_day(current):
                values.append(current)
            current += timedelta(days=1)
        return values

    def absence_streaks(self, *, scope, start, end, target_employee_id=None):
        rows = []
        for employee in self._employees(scope, target_employee_id, end):
            streak_start = None
            streak_dates = []
            for target_date in self._absence_dates(start, end):
                state = self._state(employee, target_date)
                absent = state["status"] == "ABSENT" and not state["leave"]
                if absent:
                    streak_start = streak_start or target_date
                    streak_dates.append(target_date)
                elif len(streak_dates) >= 2:
                    rows.append({
                        "employee_id": employee.id,
                        "employee_name": self._employee_name(employee),
                        "email": employee.user.email,
                        "start_date": streak_start.isoformat(),
                        "end_date": streak_dates[-1].isoformat(),
                        "working_days": len(streak_dates),
                    })
                    streak_start, streak_dates = None, []
                else:
                    streak_start, streak_dates = None, []
            if len(streak_dates) >= 2:
                rows.append({
                    "employee_id": employee.id,
                    "employee_name": self._employee_name(employee),
                    "email": employee.user.email,
                    "start_date": streak_start.isoformat(),
                    "end_date": streak_dates[-1].isoformat(),
                    "working_days": len(streak_dates),
                })
        return self._base(
            "absence_streaks", start, end,
            ["Only Monday-Friday working days are evaluated.", "Approved leave and effective attendance check-ins are excluded from absence streaks.", "Only streaks of at least two working days are returned."],
            rows,
        )

    def summary(self, *, scope, start, end, target_employee_id=None):
        rows = []
        for target_date in self._absence_dates(start, end):
            counts = {"PRESENT": 0, "INCOMPLETE": 0, "LEAVE": 0, "ABSENT": 0}
            for employee in self._employees(scope, target_employee_id, target_date):
                counts[self._state(employee, target_date)["status"]] += 1
            rows.append({"date": target_date.isoformat(), **{key.lower(): value for key, value in counts.items()}})
        return self._base(
            "summary", start, end,
            ["Counts cover active employees who had joined by each working date.", "Weekends are omitted from daily rows.", "Absence is inferred from no effective check-in and no approved leave."],
            rows,
        )

    def period_comparison(self, *, scope, end_date, target_employee_id=None):
        current_start = end_date - timedelta(days=end_date.weekday())
        current_end = current_start + timedelta(days=6)
        previous_start = current_start - timedelta(days=7)
        previous_end = current_start - timedelta(days=1)
        current = self.summary(scope=scope, start=current_start, end=min(current_end, timezone.localdate()), target_employee_id=target_employee_id)
        previous = self.summary(scope=scope, start=previous_start, end=previous_end, target_employee_id=target_employee_id)

        def totals(payload):
            result = {"present": 0, "incomplete": 0, "leave": 0, "absent": 0}
            for row in payload["rows"]:
                for key in result:
                    result[key] += row[key]
            return result

        current_totals, previous_totals = totals(current), totals(previous)
        delta = {key: current_totals[key] - previous_totals[key] for key in current_totals}
        return {
            "metric": "period_comparison",
            "date_range": {"current": _date_range(current_start, min(current_end, timezone.localdate())), "previous": _date_range(previous_start, previous_end)},
            "assumptions": current["assumptions"],
            "rows": [{"current": current_totals, "previous": previous_totals, "delta": delta}],
        }

    def execute(self, *, metric, scope, user, filters, employee_id=None):
        if metric not in METRICS:
            raise CopilotError("unsupported_metric", "That attendance metric is not supported yet.")
        today = timezone.localdate()
        if metric in {"missing_checkins", "late_employees"}:
            target = _parse_range(filters.get("date_range", {"start": today.isoformat(), "end": today.isoformat()}))[0]
            if target != today:
                raise CopilotError("invalid_date_range", "This attendance metric is available for today only.")
            return getattr(self, metric)(scope=scope, target_date=target, target_employee_id=employee_id)
        if metric == "incomplete_explanation":
            start, _ = _parse_range(filters.get("date_range", {"start": today.isoformat(), "end": today.isoformat()}))
            return self.incomplete_explanation(scope=scope, target_date=start, user=user, target_employee_id=employee_id)
        if metric == "period_comparison":
            return self.period_comparison(scope=scope, end_date=today, target_employee_id=employee_id)
        start, end = _parse_range(filters.get("date_range", {"start": today.isoformat(), "end": today.isoformat()}))
        if metric == "working_hours":
            return self.working_hours(scope=scope, start=start, end=end, user=user, target_employee_id=employee_id)
        if metric == "absence_streaks":
            return self.absence_streaks(scope=scope, start=start, end=end, target_employee_id=employee_id)
        return self.summary(scope=scope, start=start, end=end, target_employee_id=employee_id)


attendance_intelligence = AttendanceIntelligence()
