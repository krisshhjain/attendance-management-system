from datetime import datetime
from copy import deepcopy
from django.utils import timezone
from django.db import IntegrityError, transaction
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from leave_management.permissions import (
    IsEmployee, 
    IsAdminOrAppAdmin, 
    IsEmployeeWithShift,
    IsManagerOrAdmin,
    IsManagerOrSuperUser,
    IsSuperAdmin,
)

from employees.models import Employee
from .models import (
    Attendance,
    AttendanceEvent,
    AttendanceAuditLog,
    Shift,
    RegularizationRequest,
    RegularizationRequestDay,
    RegularizationQuotaPolicy,
    attendance_day_end,
    calculate_completed_working_duration,
    calculate_working_duration,
    get_effective_attendance_events,
    OfficeLocation,
)
from .geofence import validate_attendance_geofence
from .face_service import find_closest_match, verify_employee_face, FaceExtractionError, FaceLivenessError
from leave_management.models import LeaveRequest
from notifications.services import (
    queue_manager_notifications_after_commit,
    queue_notification_after_commit,
)
from system_logs.services import record_event
from accounts.scope_service import employee_in_manager_scope, filter_employees_by_manager_scope
from holidays.services import attendance_required, get_day_classification, get_day_classifications, is_company_holiday, is_working_day


def _regularization_created_message(request_obj):
    name = request_obj.employee.user.get_full_name().strip() or request_obj.employee.user.email
    return (
        f"{name} submitted a regularization request for "
        f"{request_obj.period_start or request_obj.attendance_date} to "
        f"{request_obj.period_end or request_obj.attendance_date}."
    )


def _attendance_log_state(attendance):
    return {
        "employee_id": attendance.employee_id,
        "date": attendance.date.isoformat(),
        "check_in": attendance.check_in.isoformat() if attendance.check_in else None,
        "check_out": attendance.check_out.isoformat() if attendance.check_out else None,
        "status": attendance.status,
        "working_duration": str(attendance.working_duration) if attendance.working_duration else None,
    }


def _regularization_log_state(request_obj):
    return {
        "request_id": request_obj.id,
        "employee_id": request_obj.employee_id,
        "attendance_date": request_obj.attendance_date.isoformat(),
        "request_type": request_obj.request_type,
        "status": request_obj.status,
        "requested_check_in": request_obj.requested_check_in.isoformat() if request_obj.requested_check_in else None,
        "requested_check_out": request_obj.requested_check_out.isoformat() if request_obj.requested_check_out else None,
        "approved_check_in": request_obj.approved_check_in.isoformat() if request_obj.approved_check_in else None,
        "approved_check_out": request_obj.approved_check_out.isoformat() if request_obj.approved_check_out else None,
        "reviewed_by_id": request_obj.reviewed_by_id,
        "period_type": request_obj.period_type,
        "period_start": request_obj.period_start.isoformat() if request_obj.period_start else None,
        "period_end": request_obj.period_end.isoformat() if request_obj.period_end else None,
    }


def _shift_log_state(shift):
    if shift is None:
        return None
    return {
        "shift_id": shift.id,
        "code": shift.code,
        "name": shift.name,
        "employment_type": shift.employment_type,
        "start_time": shift.start_time.strftime("%H:%M"),
        "end_time": shift.end_time.strftime("%H:%M"),
        "is_active": shift.is_active,
    }


def _location_log_state(location):
    return {
        "location_id": location.id,
        "name": location.name,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "radius_meters": location.radius_meters,
        "is_active": location.is_active,
    }


def _queue_regularization_outcome(request_obj, status_value, reason=""):
    if status_value == "APPROVED":
        title = "Regularization request approved"
        message = (
            f"Your regularization request for {request_obj.attendance_date} "
            "was approved."
        )
    else:
        title = "Regularization request rejected"
        message = (
            f"Your regularization request for {request_obj.attendance_date} "
            "was rejected."
        )
        if reason:
            message += f" Reason: {reason}"

    queue_notification_after_commit(
        user=request_obj.employee.user,
        title=title,
        message=message,
        notification_type="REGULARIZATION",
        email_subject=title,
        email_body=message,
    )


def _get_last_event_state(employee, date):
    """Determine check-in/check-out state from events or attendance record.
    Returns: (state, last_event) where state is:
      - 'CHECKED_IN'   : currently checked in (has CHECK_IN, no CHECK_OUT)
      - 'CHECKED_OUT'  : already checked out (has CHECK_OUT)
      - 'NOT_CHECKED_IN' : no check-in today
    """
    event_rows = get_effective_attendance_events(employee, date)
    last_event = event_rows[-1] if event_rows else None

    if last_event:
        if last_event.event_type == "CHECK_IN":
            return 'CHECKED_IN', last_event
        else:  # CHECK_OUT
            return 'CHECKED_OUT', last_event

    # Fallback: check Attendance record for backward compatibility
    try:
        attendance = Attendance.objects.get(employee=employee, date=date)
        if attendance.check_out:
            return 'CHECKED_OUT', None
        if attendance.check_in:
            return 'CHECKED_IN', None
        return 'NOT_CHECKED_IN', None
    except Attendance.DoesNotExist:
        return 'NOT_CHECKED_IN', None


def _get_previous_incomplete_attendance(employee, target_date):
    """Return the most recent prior attendance with an unmatched check-in."""
    candidates = Attendance.objects.filter(
        employee=employee,
        date__lt=target_date,
        check_in__isnull=False,
    ).order_by("-date")

    for attendance in candidates:
        state, _ = _get_last_event_state(employee, attendance.date)
        if attendance.status == "INCOMPLETE" and state == "CHECKED_IN":
            return {
                "date": attendance.date,
                "check_in": attendance.check_in,
                "status": attendance.status,
                "needs_regularization": True,
            }
    return None
class CheckInView(APIView):
    permission_classes = [IsEmployee]
    app_access_key = "attendance"

    def post(self, request):
        if not hasattr(request.user, "employee"):
            return Response(
                {"error": "No employee profile associated with this account."},
                status=403,
            )
        employee = request.user.employee
        today = timezone.localdate()

        # Geofence verification
        is_valid, error_msg, distance, coords = validate_attendance_geofence(
            request.data.get("latitude"),
            request.data.get("longitude"),
            request.data.get("accuracy"),
        )
        if not is_valid:
            return Response({"error": error_msg}, status=400)

        # Get or create attendance record
        attendance, created = Attendance.get_or_create_for_date(employee, today)
        before_state = _attendance_log_state(attendance)

        if attendance.status == "LEAVE" or (attendance.status == "ABSENT" and is_working_day(today)):
            return Response(
                {"error": "You cannot check in because your attendance is marked as " + attendance.status.lower() + " today."},
                status=400,
            )

        has_approved_leave = LeaveRequest.objects.filter(
            employee=employee,
            status="APPROVED",
            start_date__lte=today,
            end_date__gte=today,
        ).exists()

        if has_approved_leave:
            return Response(
                {"error": "You cannot check in because you are on approved leave today."},
                status=400,
            )

        # Check if employee has an effective shift
        effective_shift = employee.get_effective_shift()
        if effective_shift is None:
            return Response(
                {"error": "You must have a shift assigned before checking in. Please self-assign a shift or contact admin."},
                status=400,
            )

        # Check current state via events
        state, last_event = _get_last_event_state(employee, today)
        if state == 'CHECKED_IN':
            return Response(
                {"error": "Already checked in"},
                status=400,
            )

        lat, lon, acc = coords
        now = timezone.now()

        # Create AttendanceEvent with effective shift
        with transaction.atomic():
            AttendanceEvent.objects.create(
                employee=employee,
                shift=effective_shift,
                timestamp=now,
                event_type="CHECK_IN",
                source="MOBILE",
                latitude=lat,
                longitude=lon,
                accuracy=acc,
                distance=distance,
            )
            # Recompute attendance summary
            attendance.recompute_from_events()

        attendance.refresh_from_db()
        record_event(
            event_type="CHECK_IN",
            category="ATTENDANCE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Attendance check-in recorded.",
            source="MOBILE",
            request=request,
            before_state=before_state,
            after_state=_attendance_log_state(attendance),
        )
        return Response(
            {
                "message": "Attendance marked successfully.",
                "check_in": attendance.check_in,
            },
            status=201,
        )

class CheckOutView(APIView):
    permission_classes = [IsEmployee]
    app_access_key = "attendance"

    def post(self, request):
        if not hasattr(request.user, "employee"):
            return Response(
                {"error": "No employee profile associated with this account."},
                status=403,
            )
        employee = request.user.employee
        today = timezone.localdate()

        # Geofence verification
        is_valid, error_msg, distance, coords = validate_attendance_geofence(
            request.data.get("latitude"),
            request.data.get("longitude"),
            request.data.get("accuracy"),
        )
        if not is_valid:
            return Response({"error": error_msg}, status=400)

        try:
            attendance = Attendance.objects.get(
                employee=employee,
                date=today,
            )
        except Attendance.DoesNotExist:
            return Response(
                {"error": "You have not checked in today"},
                status=400,
            )
        before_state = _attendance_log_state(attendance)

        # Check current state via events
        state, last_event = _get_last_event_state(employee, today)
        if state == 'NOT_CHECKED_IN':
            return Response(
                {"error": "You have not checked in today"},
                status=400,
            )
        if state == 'CHECKED_OUT':
            return Response(
                {"error": "Already checked out today"},
                status=400,
            )

        lat, lon, acc = coords
        now = timezone.now()
        
        # Get effective shift for event recording
        effective_shift = employee.get_effective_shift()

        with transaction.atomic():
            AttendanceEvent.objects.create(
                employee=employee,
                shift=effective_shift,
                timestamp=now,
                event_type="CHECK_OUT",
                source="MOBILE",
                latitude=lat,
                longitude=lon,
                accuracy=acc,
                distance=distance,
            )
            attendance.recompute_from_events()

        attendance.refresh_from_db()
        record_event(
            event_type="CHECK_OUT",
            category="ATTENDANCE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Attendance check-out recorded.",
            source="MOBILE",
            request=request,
            before_state=before_state,
            after_state=_attendance_log_state(attendance),
        )
        return Response(
            {
                "message": "Check-out successful",
                "check_in": attendance.check_in,
                "check_out": attendance.check_out,
                "working_duration": attendance.working_duration,
            },
            status=200,
        )

class TodayAttendanceView(APIView):
    permission_classes = [IsEmployee]
    app_access_key = "attendance"

    def get(self, request):
        if not hasattr(request.user, "employee"):
            return Response({
                "status": "NOT_CHECKED_IN",
                "check_in": None,
                "check_out": None,
                "working_duration": None,
            })
        employee = request.user.employee
        today = timezone.localdate()
        day_classification = get_day_classification(today)
        working_day = day_classification["is_working_day"]
        previous_incomplete = _get_previous_incomplete_attendance(employee, today)

        try:
            attendance = Attendance.objects.get(
                employee=employee,
                date=today,
            )
        except Attendance.DoesNotExist:
            # Always return NOT_CHECKED_IN - weekends should allow attendance if employee comes to office
            return Response({
                "status": day_classification["day_type"] if not working_day else "NOT_CHECKED_IN",
                "check_in": None,
                "check_out": None,
                "working_duration": None,
                "is_working_day": working_day,
                "attendance_required": day_classification["attendance_required"],
                "day_type": day_classification["day_type"],
                "holiday_name": day_classification["holiday_name"],
                "previous_incomplete_attendance": previous_incomplete,
            })

        events = get_effective_attendance_events(employee, today)
        working_duration = calculate_working_duration(
            events,
            end_at=attendance_day_end(today),
        )
        completed_working_duration = calculate_completed_working_duration(events)
        active_check_in = events[-1].timestamp if events and events[-1].event_type == "CHECK_IN" else None
        state, last_event = _get_last_event_state(employee, today)

        if attendance.status == "LEAVE":
            status = "LEAVE"
        elif state == "NOT_CHECKED_IN":
            status = day_classification["day_type"] if not working_day else (
                "ABSENT" if attendance.status == "ABSENT" else "NOT_CHECKED_IN"
            )
        elif state == "CHECKED_OUT":
            status = "COMPLETED"
        else:
            status = "CHECKED_IN"

        return Response({
            "status": status,
            "check_in": attendance.check_in,
            "check_out": attendance.check_out,
            "working_duration": working_duration,
            "completed_working_duration": completed_working_duration,
            "active_check_in": active_check_in,
            "is_working_day": working_day,
            "attendance_required": day_classification["attendance_required"],
            "day_type": day_classification["day_type"],
            "holiday_name": day_classification["holiday_name"],
            "previous_incomplete_attendance": previous_incomplete,
        })

class MyTeamView(APIView):
    """
    GET /api/attendance/my-team/

    Returns today's status for every active employee who shares the same
    employment_type AND section as the requesting employee.
    subsection is intentionally ignored so that A1, A2, A3 … all appear.

    Classification rules (applied in priority order):
      - ON_LEAVE      : has an APPROVED LeaveRequest covering today
      - CHECKED_IN    : has a today Attendance record with check_in set
                        (includes both still-checked-in and already-checked-out)
      - WEEKEND       : today is Saturday/Sunday and employee has no attendance
      - HOLIDAY       : today is an active company holiday and employee has no attendance
      - YET_TO_CHECK_IN : active team member with no check_in today and not on leave
    """
    permission_classes = [IsEmployee]
    app_access_key = "attendance"

    def get(self, request):
        me = request.user.employee
        today = timezone.localdate()

        # Guard: employee must have both fields set
        if not me.employment_type or not me.section:
            return Response(
                {
                    "team_employment_type": me.employment_type or "",
                    "team_section": me.section or "",
                    "total_members": 0,
                    "checked_in_count": 0,
                    "yet_to_check_in_count": 0,
                    "on_leave_count": 0,
                    "members": [],
                    "note": "Team information is incomplete for this employee.",
                },
                status=200,
            )

        # Fetch all active team members — same type + section, any subsection
        teammates = (
            Employee.objects.select_related("user")
            .filter(
                is_active=True,
                employment_type=me.employment_type,
                section=me.section,
            )
        )

        teammate_ids = list(teammates.values_list("id", flat=True))

        # Prefetch today's attendance for the whole team in one query
        attendance_map = {
            att.employee_id: att
            for att in Attendance.objects.filter(
                employee_id__in=teammate_ids,
                date=today,
            )
        }

        # Employees with approved leave covering today (any half-day type included)
        on_leave_ids = set(
            LeaveRequest.objects.filter(
                employee_id__in=teammate_ids,
                status="APPROVED",
                start_date__lte=today,
                end_date__gte=today,
            ).values_list("employee_id", flat=True)
        )

        # Build per-member leave type label for UI
        approved_leave_by_employee = {}
        for lr in LeaveRequest.objects.select_related("leave_type").filter(
            employee_id__in=on_leave_ids,
            status="APPROVED",
            start_date__lte=today,
            end_date__gte=today,
        ):
            approved_leave_by_employee[lr.employee_id] = lr.leave_type.name

        members = []
        checked_in_count = 0
        yet_to_check_in_count = 0
        on_leave_count = 0
        
        # Check if today is a weekend (Saturday=5, Sunday=6)
        day_classification = get_day_classification(today)

        for emp in teammates:
            att = attendance_map.get(emp.id)
            full_name = f"{emp.user.first_name} {emp.user.last_name}".strip() or emp.user.email

            if emp.id in on_leave_ids:
                member_status = "ON_LEAVE"
                on_leave_count += 1
            elif att is not None and att.check_in is not None:
                member_status = "CHECKED_IN"
                checked_in_count += 1
            elif day_classification["day_type"] in {"WEEKEND", "HOLIDAY"}:
                # Non-required dates are represented distinctly and excluded from missing counts.
                member_status = day_classification["day_type"]
            else:
                member_status = "YET_TO_CHECK_IN"
                yet_to_check_in_count += 1

            member_data = {
                "id": emp.id,
                "name": full_name,
                "department": emp.department,
                "subsection": emp.subsection,
                "status": member_status,
                "day_type": day_classification["day_type"],
                "holiday_name": day_classification["holiday_name"],
                "attendance_required": day_classification["attendance_required"],
                "check_in_time": att.check_in.isoformat() if att and att.check_in else None,
                "check_out_time": att.check_out.isoformat() if att and att.check_out else None,
            }

            if member_status == "ON_LEAVE":
                member_data["leave_type"] = approved_leave_by_employee.get(emp.id, "Leave")

            members.append(member_data)

        return Response(
            {
                "team_employment_type": me.employment_type,
                "team_section": me.section,
                "total_members": len(members),
                "checked_in_count": checked_in_count,
                "yet_to_check_in_count": yet_to_check_in_count,
                "on_leave_count": on_leave_count,
                "members": members,
                "current_user_id": me.id,
            },
            status=200,
        )


class IsEmployeeOrManager(BasePermission):
    """Allow employees or managers."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # Allow managers and admins
        if request.user.is_staff or getattr(request.user, 'is_system_admin', False) or request.user.is_superuser:
            return True
        # Allow employees with app access
        try:
            employee = request.user.employee
            app_key = getattr(view, 'app_access_key', None)
            if app_key:
                return employee.is_active and employee.app_access.get(app_key, False)
            return employee.is_active
        except Employee.DoesNotExist:
            return False


class AttendanceHistoryView(APIView):
    """View attendance history - accessible by employees and managers."""
    permission_classes = [IsEmployeeOrManager]
    app_access_key = "attendance"

    def get(self, request):
        # Check if user is a manager or admin
        is_manager_or_admin = request.user.is_staff or request.user.is_system_admin
        
        if is_manager_or_admin:
            manager_scoped = request.user.is_system_admin and not request.user.is_superuser
            employee_scope = filter_employees_by_manager_scope(request.user, Employee.objects.all()) if manager_scoped else None
            # Managers/admins see all employees' attendance
            # Check for employee_id filter
            employee_id = request.query_params.get('employee_id')
            if employee_id:
                try:
                    attendance_records = Attendance.objects.filter(employee_id=employee_id)
                    if employee_scope is not None:
                        attendance_records = attendance_records.filter(employee_id__in=employee_scope.values("id"))
                    attendance_records = attendance_records.select_related('employee__user').order_by("-date")
                except ValueError:
                    return Response({"error": "Invalid employee_id"}, status=400)
            else:
                # Return all employees' attendance
                attendance_records = Attendance.objects.select_related('employee__user').order_by("-date")
                if employee_scope is not None:
                    attendance_records = attendance_records.filter(employee_id__in=employee_scope.values("id"))
        else:
            # Regular employees see only their own attendance
            if not hasattr(request.user, "employee"):
                return Response([])
            employee = request.user.employee
            attendance_records = Attendance.objects.filter(
                employee=employee
            ).order_by("-date")

        data = []
        day_classifications = get_day_classifications(attendance_records.values_list("date", flat=True).distinct())
        for attendance in attendance_records:
            events = get_effective_attendance_events(attendance.employee, attendance.date)
            day_classification = day_classifications[attendance.date]
            displayed_status = attendance.status
            if attendance.status != "LEAVE" and not attendance.check_in and not day_classification["attendance_required"]:
                displayed_status = day_classification["day_type"]
            record = {
                "date": attendance.date,
                "status": displayed_status,
                "day_type": day_classification["day_type"],
                "holiday_name": day_classification["holiday_name"],
                "attendance_required": day_classification["attendance_required"],
                "check_in": attendance.check_in,
                "check_out": attendance.check_out,
                "working_duration": calculate_working_duration(
                    events,
                    end_at=attendance_day_end(attendance.date),
                ),
            }
            # Add employee info for managers/admins
            if is_manager_or_admin:
                record["employee_id"] = attendance.employee.id
                record["employee_name"] = f"{attendance.employee.user.first_name} {attendance.employee.user.last_name}"
                record["employee_email"] = attendance.employee.user.email
            
            data.append(record)

        return Response(data)

class AdminAttendanceView(APIView):
    """Manager and Admin can view attendance records."""
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        date_param = request.query_params.get("date")
        if not date_param:
            filter_date = timezone.localdate()
        else:
            from datetime import date as date_type
            try:
                filter_date = date_type.fromisoformat(date_param)
            except ValueError:
                return Response(
                    {"error": f"Invalid date '{date_param}'. Expected format: YYYY-MM-DD."},
                    status=400,
                )

        employees = Employee.objects.filter(is_active=True).select_related("user")
        if request.user.is_system_admin and not request.user.is_superuser:
            employees = filter_employees_by_manager_scope(request.user, employees)
        attendance_records = Attendance.objects.filter(date=filter_date).select_related("employee")
        attendance_map = {att.employee_id: att for att in attendance_records}
        day_classification = get_day_classification(filter_date)

        data = []
        for emp in employees:
            att = attendance_map.get(emp.id)
            events = get_effective_attendance_events(emp, filter_date)
            
            # Determine actual display status
            if att:
                if att.status == "LEAVE":
                    status_display = att.status
                elif not att.check_in and day_classification["day_type"] != "WORKING_DAY":
                    status_display = day_classification["day_type"]
                elif att.status == "ABSENT":
                    status_display = att.status
                elif att.check_in is None:
                    status_display = "ABSENT"
                else:
                    status_display = att.status # PRESENT or INCOMPLETE
            else:
                status_display = day_classification["day_type"] if day_classification["day_type"] != "WORKING_DAY" else "ABSENT"
                
            data.append({
                "employee": emp.user.email,
                "employee_name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
                "section": emp.section,
                "subsection": emp.subsection,
                "date": filter_date,
                "status": status_display,
                "day_type": day_classification["day_type"],
                "holiday_name": day_classification["holiday_name"],
                "attendance_required": day_classification["attendance_required"],
                "check_in": att.check_in if att else None,
                "check_out": att.check_out if att else None,
                "working_duration": str(calculate_working_duration(
                    events,
                    end_at=attendance_day_end(filter_date),
                )) if att else None,
            })

        # Sort: Present first, then Incomplete, then Absent/Leave
        data.sort(key=lambda x: (
            0 if x["status"] == "PRESENT" else 1 if x["status"] == "INCOMPLETE" else 2,
            x["employee_name"]
        ))
        
        return Response(data)


class AdminDashboardView(APIView):
    """Manager and Admin can view dashboard."""
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        today = timezone.localdate()
        day_classification = get_day_classification(today)

        scoped = request.user.is_system_admin and not request.user.is_superuser
        employees = Employee.objects.all()
        if scoped:
            employees = filter_employees_by_manager_scope(request.user, employees)
        total_employees = employees.count()
        active_employees = employees.filter(is_active=True).count()

        today_attendance = Attendance.objects.filter(date=today)
        if scoped:
            today_attendance = today_attendance.filter(employee_id__in=employees.values("id"))

        present_today = today_attendance.filter(
            status="PRESENT"
        ).count()

        checked_in_today = today_attendance.filter(
            status="INCOMPLETE",
            check_in__isnull=False,
            check_out__isnull=True,
        ).count()

        completed_today = today_attendance.filter(
            check_in__isnull=False,
            check_out__isnull=False,
        ).count()

        attendance_records = today_attendance.select_related("employee", "employee__user").order_by("-check_in")
        attendance_data = []
        for attendance in attendance_records:
            events = get_effective_attendance_events(attendance.employee, today)
            displayed_status = attendance.status
            if attendance.status != "LEAVE" and not attendance.check_in and not day_classification["attendance_required"]:
                displayed_status = day_classification["day_type"]
            working_duration = calculate_working_duration(
                events,
                end_at=attendance_day_end(today),
            )
            attendance_data.append({
                "employee": attendance.employee.user.email,
                "section": attendance.employee.section,
                "subsection": attendance.employee.subsection,
                "date": attendance.date,
                "status": displayed_status,
                "check_in": attendance.check_in,
                "check_out": attendance.check_out,
                "working_duration": str(working_duration) if working_duration is not None else None,
            })

        return Response({
            "total_employees": total_employees,
            "active_employees": active_employees,
            "present_today": present_today,
            "checked_in_today": checked_in_today,
            "completed_today": completed_today,
            "attendance": attendance_data,
            "is_working_day": day_classification["is_working_day"],
            "attendance_required": day_classification["attendance_required"],
            "day_type": day_classification["day_type"],
            "holiday_name": day_classification["holiday_name"],
        })

class AdminResetAttendanceView(APIView):
    """Only SuperUser can reset attendance - Manager cannot."""
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        employee_email = request.data.get("employee")
        reason = request.data.get("reason")

        if not employee_email or not reason:
            return Response({"error": "Employee email and reason are required"}, status=400)

        today = timezone.localdate()
        try:
            attendance = Attendance.objects.get(employee__user__email=employee_email, date=today)
        except Attendance.DoesNotExist:
            return Response({"error": "No attendance record found for today"}, status=404)

        reset_type = request.data.get("reset_type", "both")
        target_employee = attendance.employee

        previous_data = {
            "check_in": str(attendance.check_in) if attendance.check_in else None,
            "check_out": str(attendance.check_out) if attendance.check_out else None,
            "status": attendance.status,
            "working_duration": str(attendance.working_duration) if attendance.working_duration else None,
        }

        with transaction.atomic():
            if reset_type == "checkout_only":
                attendance.check_out = None
                attendance.status = "INCOMPLETE"
                attendance.working_duration = None
                attendance.save()
            else:
                # Full wipe - delete events and attendance
                AttendanceEvent.objects.filter(
                    employee=attendance.employee,
                    timestamp__date=today
                ).delete()
                attendance.delete()
                attendance = None

            from .models import AttendanceCorrection
            AttendanceCorrection.objects.create(
                attendance=attendance,
                admin_user=request.user,
                correction_type="RESET",
                reason=reason,
                previous_data=previous_data
            )

        record_event(
            event_type="ATTENDANCE_RESET",
            category="ATTENDANCE",
            severity="WARNING",
            status="SUCCESS",
            actor=request.user,
            target=target_employee,
            message="Attendance record reset by an administrator.",
            source="ADMIN",
            request=request,
            before_state=previous_data,
            after_state={"reset_type": reset_type, "attendance_exists": attendance is not None},
        )

        return Response({"message": "Attendance successfully reset for today."})

class AdminEditAttendanceView(APIView):
    """SuperUser-only past attendance correction."""
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        employee_email = request.data.get("employee")
        date_str = request.data.get("date")
        reason = request.data.get("reason")
        check_in_str = request.data.get("check_in")
        check_out_str = request.data.get("check_out")
        status = request.data.get("status")

        if not all([employee_email, date_str, reason, status]):
            return Response({"error": "Employee email, date, status, and reason are required"}, status=400)

        from datetime import date, datetime
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        if str(status).upper() == "ABSENT" and not attendance_required(target_date):
            day = get_day_classification(target_date)
            return Response({"error": f"Cannot mark an employee absent on a {day['day_type'].lower()} date."}, status=400)
            
        if target_date > timezone.localdate():
            return Response({"error": "Cannot edit future attendance."}, status=400)

        try:
            attendance = Attendance.objects.get(employee__user__email=employee_email, date=target_date)
        except Attendance.DoesNotExist:
            from employees.models import Employee
            try:
                emp = Employee.objects.get(user__email=employee_email)
                attendance = Attendance(employee=emp, date=target_date)
            except Employee.DoesNotExist:
                return Response({"error": "Employee not found"}, status=404)

        previous_data = {
            "check_in": str(attendance.check_in) if attendance.check_in else None,
            "check_out": str(attendance.check_out) if attendance.check_out else None,
            "status": attendance.status,
            "working_duration": str(attendance.working_duration) if attendance.working_duration else None,
        }

        parsed_check_in = None
        if check_in_str:
            try:
                parsed_check_in = datetime.fromisoformat(check_in_str.replace('Z', '+00:00'))
            except ValueError:
                return Response({"error": "Invalid check_in time format"}, status=400)

        parsed_check_out = None
        if check_out_str:
            try:
                parsed_check_out = datetime.fromisoformat(check_out_str.replace('Z', '+00:00'))
            except ValueError:
                return Response({"error": "Invalid check_out time format"}, status=400)

        with transaction.atomic():
            # Remove any existing ADMIN events for this day to allow a clean override
            AttendanceEvent.objects.filter(
                employee=attendance.employee,
                timestamp__date=target_date,
                source="ADMIN"
            ).delete()

            effective_shift = attendance.employee.get_effective_shift()

            if parsed_check_in:
                AttendanceEvent.objects.create(
                    employee=attendance.employee,
                    shift=effective_shift,
                    timestamp=parsed_check_in,
                    event_type="CHECK_IN",
                    source="ADMIN",
                )

            if parsed_check_out:
                AttendanceEvent.objects.create(
                    employee=attendance.employee,
                    shift=effective_shift,
                    timestamp=parsed_check_out,
                    event_type="CHECK_OUT",
                    source="ADMIN",
                )

            attendance.recompute_from_events()

            # Apply final status logic
            if status in ["ABSENT", "LEAVE"]:
                attendance.status = status
            elif parsed_check_in and parsed_check_out:
                if status == "INCOMPLETE":
                    attendance.status = "PRESENT"
                else:
                    attendance.status = status
            else:
                attendance.status = status

            attendance.save()

        from .models import AttendanceCorrection
        AttendanceCorrection.objects.create(
            attendance=attendance,
            admin_user=request.user,
            correction_type="EDIT",
            reason=reason,
            previous_data=previous_data
        )

        record_event(
            event_type="ATTENDANCE_EDIT",
            category="ATTENDANCE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=attendance.employee,
            message="Attendance record edited by an administrator.",
            source="ADMIN",
            request=request,
            before_state=previous_data,
            after_state=_attendance_log_state(attendance),
        )

        return Response({"message": "Attendance successfully edited."})

class AdminForceCheckoutView(APIView):
    """Manager and Admin can force checkout."""
    permission_classes = [IsManagerOrAdmin]

    def post(self, request):
        date_param = request.data.get("date")
        if not date_param:
            target_date = timezone.localdate()
        else:
            from datetime import date as date_type
            try:
                target_date = date_type.fromisoformat(date_param)
            except ValueError:
                return Response({"error": "Invalid date format"}, status=400)
                
        is_all = request.data.get("all", False)
        employee_email = request.data.get("employee")

        if employee_email and request.user.is_system_admin and not request.user.is_superuser:
            target = Employee.objects.filter(user__email=employee_email).first()
            if target is not None and not employee_in_manager_scope(request.user, target):
                return Response({"error": "You do not have access to this employee."}, status=403)

        # The summary row's ``check_out`` is the latest checkout for the day,
        # not necessarily the checkout for the currently open interval.  An
        # employee can check in again after an earlier checkout, so determine
        # active attendance from the latest event instead of summary fields.
        candidate_attendances = Attendance.objects.filter(
            date=target_date,
            check_in__isnull=False,
        ).select_related("employee", "employee__user")
        if request.user.is_system_admin and not request.user.is_superuser:
            candidate_attendances = candidate_attendances.filter(
                employee_id__in=filter_employees_by_manager_scope(
                    request.user, Employee.objects.all()
                ).values("id")
            )
        active_attendances = [
            attendance
            for attendance in candidate_attendances
            if _get_last_event_state(attendance.employee, target_date)[0] == "CHECKED_IN"
        ]

        if is_all:
            attendances = active_attendances
        elif employee_email:
            attendances = [
                attendance
                for attendance in active_attendances
                if attendance.employee.user.email == employee_email
            ]
            if not attendances:
                return Response({"error": "No active check-in found for this employee on this date"}, status=404)
        else:
            return Response({"error": "Must provide 'all': true or 'employee': email"}, status=400)

        count = 0
        now = timezone.now()
        for att in attendances:
            before_state = _attendance_log_state(att)
            # Get effective shift for each employee
            effective_shift = att.employee.get_effective_shift()
            with transaction.atomic():
                AttendanceEvent.objects.create(
                    employee=att.employee,
                    shift=effective_shift,
                    timestamp=now,
                    event_type="CHECK_OUT",
                    source="ADMIN",
                )
                att.recompute_from_events()
            att.refresh_from_db()
            record_event(
                event_type="ADMIN_FORCE_CHECKOUT",
                category="ATTENDANCE",
                severity="WARNING",
                status="SUCCESS",
                actor=request.user,
                target=att.employee,
                message="Attendance check-out was forced by an administrator.",
                source="ADMIN",
                request=request,
                before_state=before_state,
                after_state=_attendance_log_state(att),
            )
            count += 1
            
        return Response({"message": f"Successfully forced check-out for {count} records", "count": count})
class WebsiteFacialCheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = request.user.employee
        today = timezone.localdate()

        frames = request.data.get("frames")
        captured_at_ms = request.data.get("captured_at_ms")
        if not frames:
            return Response({"error": "No camera frames provided"}, status=400)

        # Geofence verification
        is_valid, error_msg, distance_geo, coords = validate_attendance_geofence(
            request.data.get("latitude"),
            request.data.get("longitude"),
            request.data.get("accuracy"),
        )
        if not is_valid:
            return Response({"error": error_msg}, status=400)

        # 1. Verify face matches authenticated user
        try:
            is_match, distance = verify_employee_face(employee, frames, captured_at_ms=captured_at_ms)
        except FaceLivenessError as e:
            status_code = 503 if e.status == "liveness_error" else 400
            return Response({"status": e.status, "error": str(e)}, status=status_code)
        except FaceExtractionError as e:
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            return Response({"error": "Internal server error"}, status=500)

        if not is_match:
            return Response({"error": "Recognized face does not match your authenticated account."}, status=403)

        # Get or create attendance record
        attendance, created = Attendance.get_or_create_for_date(employee, today)
        before_state = _attendance_log_state(attendance)

        if attendance.status == "LEAVE" or (attendance.status == "ABSENT" and is_working_day(today)):
            return Response(
                {"error": "You cannot check in because your attendance is marked as " + attendance.status.lower() + " today."},
                status=400,
            )

        has_approved_leave = LeaveRequest.objects.filter(
            employee=employee,
            status="APPROVED",
            start_date__lte=today,
            end_date__gte=today,
        ).exists()

        if has_approved_leave:
            return Response(
                {"error": "You cannot check in because you are on approved leave today."},
                status=400,
            )

        # Check current state via events
        state, last_event = _get_last_event_state(employee, today)
        if state == 'CHECKED_IN':
            return Response(
                {"error": "Already checked in today"},
                status=400,
            )

        lat, lon, acc = coords
        now = timezone.now()
        
        # Get effective shift for event recording
        effective_shift = employee.get_effective_shift()

        with transaction.atomic():
            AttendanceEvent.objects.create(
                employee=employee,
                shift=effective_shift,
                timestamp=now,
                event_type="CHECK_IN",
                source="FACE_WEB",
                latitude=lat,
                longitude=lon,
                accuracy=acc,
                distance=distance_geo,
            )
            attendance.recompute_from_events()

        attendance.refresh_from_db()
        record_event(
            event_type="CHECK_IN",
            category="ATTENDANCE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Facial attendance check-in recorded.",
            source="FACE_WEB",
            request=request,
            before_state=before_state,
            after_state=_attendance_log_state(attendance),
        )
        return Response(
            {
                "message": "Check-in successful",
                "check_in": attendance.check_in,
            },
            status=201,
        )

class WebsiteFacialCheckOutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = request.user.employee
        today = timezone.localdate()

        frames = request.data.get("frames")
        captured_at_ms = request.data.get("captured_at_ms")
        if not frames:
            return Response({"error": "No camera frames provided"}, status=400)

        # Geofence verification
        is_valid, error_msg, distance_geo, coords = validate_attendance_geofence(
            request.data.get("latitude"),
            request.data.get("longitude"),
            request.data.get("accuracy"),
        )
        if not is_valid:
            return Response({"error": error_msg}, status=400)

        # 1. Verify face matches authenticated user
        try:
            is_match, distance = verify_employee_face(employee, frames, captured_at_ms=captured_at_ms)
        except FaceLivenessError as e:
            status_code = 503 if e.status == "liveness_error" else 400
            return Response({"status": e.status, "error": str(e)}, status=status_code)
        except FaceExtractionError as e:
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            return Response({"error": "Internal server error"}, status=500)

        if not is_match:
            return Response({"error": "Recognized face does not match your authenticated account."}, status=403)

        try:
            attendance = Attendance.objects.get(
                employee=employee,
                date=today,
            )
        except Attendance.DoesNotExist:
            return Response(
                {"error": "You have not checked in today"},
                status=400,
            )
        before_state = _attendance_log_state(attendance)

        # Check current state via events
        state, last_event = _get_last_event_state(employee, today)
        if state == 'NOT_CHECKED_IN':
            return Response(
                {"error": "You have not checked in today"},
                status=400,
            )
        if state == 'CHECKED_OUT':
            return Response(
                {"error": "Already checked out today"},
                status=400,
            )

        lat, lon, acc = coords
        now = timezone.now()
        
        # Get effective shift for event recording
        effective_shift = employee.get_effective_shift()

        with transaction.atomic():
            AttendanceEvent.objects.create(
                employee=employee,
                shift=effective_shift,
                timestamp=now,
                event_type="CHECK_OUT",
                source="FACE_WEB",
                latitude=lat,
                longitude=lon,
                accuracy=acc,
                distance=distance_geo,
            )
            attendance.recompute_from_events()

        attendance.refresh_from_db()
        record_event(
            event_type="CHECK_OUT",
            category="ATTENDANCE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Facial attendance check-out recorded.",
            source="FACE_WEB",
            request=request,
            before_state=before_state,
            after_state=_attendance_log_state(attendance),
        )
        return Response(
            {
                "message": "Check-out successful",
                "check_in": attendance.check_in,
                "check_out": attendance.check_out,
                "working_duration": attendance.working_duration,
            },
            status=200,
        )


class KioskFaceCheckInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        frames = request.data.get("frames")
        captured_at_ms = request.data.get("captured_at_ms")
        if not frames:
            return Response({"error": "No camera frames provided"}, status=400)

        try:
            employee, distance = find_closest_match(frames, captured_at_ms=captured_at_ms)
        except FaceLivenessError as e:
            AttendanceAuditLog.objects.create(
                event_type="CHECK_IN",
                status="FAILED_ERROR",
                error_message=str(e),
            )
            status_code = 503 if e.status == "liveness_error" else 400
            return Response({"status": e.status, "error": str(e)}, status=status_code)
        except FaceExtractionError as e:
            AttendanceAuditLog.objects.create(
                event_type="CHECK_IN",
                status="FAILED_MULTI_FACE" if "multi-face" in str(e).lower() else "FAILED_NO_FACE",
                error_message=str(e)
            )
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            AttendanceAuditLog.objects.create(
                event_type="CHECK_IN",
                status="FAILED_ERROR",
                error_message=str(e)
            )
            return Response({"error": "Internal server error"}, status=500)

        if not employee:
            AttendanceAuditLog.objects.create(
                event_type="CHECK_IN",
                status="FAILED_UNKNOWN",
                distance=distance,
            )
            return Response({"error": "Face not recognized."}, status=403)

        today = timezone.localdate()
        attendance, created = Attendance.get_or_create_for_date(employee, today)

        from leave_management.models import LeaveRequest
        has_approved_leave = LeaveRequest.objects.filter(
            employee=employee,
            status="APPROVED",
            start_date__lte=today,
            end_date__gte=today,
        ).exists()

        if has_approved_leave:
            return Response(
                {"error": f"Hello {employee.user.first_name}, you cannot check in because you are on approved leave today."},
                status=400,
            )

        # Check if employee has an effective shift
        effective_shift = employee.get_effective_shift()
        if effective_shift is None:
            return Response(
                {"error": "You must have a shift assigned before checking in. Please contact admin."},
                status=400,
            )

        # Check current state via events
        state, _ = _get_last_event_state(employee, today)
        if state == 'CHECKED_IN':
            return Response(
                {"error": f"Hello {employee.user.first_name}, you are already checked in today."},
                status=400,
            )

        now = timezone.now()

        with transaction.atomic():
            AttendanceEvent.objects.create(
                employee=employee,
                shift=effective_shift,
                timestamp=now,
                event_type="CHECK_IN",
                source="KIOSK",
            )
            attendance.recompute_from_events()

        AttendanceAuditLog.objects.create(
            event_type="CHECK_IN",
            status="SUCCESS",
            employee=employee,
            distance=distance,
        )

        attendance.refresh_from_db()
        record_event(
            event_type="CHECK_IN",
            category="ATTENDANCE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Kiosk attendance check-in recorded.",
            source="KIOSK",
            request=request,
            after_state=_attendance_log_state(attendance),
        )
        return Response(
            {
                "message": f"Welcome, {employee.user.first_name}!",
                "check_in": attendance.check_in,
            },
            status=201,
        )


class KioskFaceCheckOutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        frames = request.data.get("frames")
        captured_at_ms = request.data.get("captured_at_ms")
        if not frames:
            return Response({"error": "No camera frames provided"}, status=400)

        try:
            employee, distance = find_closest_match(frames, captured_at_ms=captured_at_ms)
        except FaceLivenessError as e:
            AttendanceAuditLog.objects.create(
                event_type="CHECK_OUT",
                status="FAILED_ERROR",
                error_message=str(e),
            )
            status_code = 503 if e.status == "liveness_error" else 400
            return Response({"status": e.status, "error": str(e)}, status=status_code)
        except FaceExtractionError as e:
            AttendanceAuditLog.objects.create(
                event_type="CHECK_OUT",
                status="FAILED_MULTI_FACE" if "multi-face" in str(e).lower() else "FAILED_NO_FACE",
                error_message=str(e)
            )
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            AttendanceAuditLog.objects.create(
                event_type="CHECK_OUT",
                status="FAILED_ERROR",
                error_message=str(e)
            )
            return Response({"error": "Internal server error"}, status=500)

        if not employee:
            AttendanceAuditLog.objects.create(
                event_type="CHECK_OUT",
                status="FAILED_UNKNOWN",
                distance=distance,
            )
            return Response({"error": "Face not recognized."}, status=403)

        today = timezone.localdate()
        try:
            attendance = Attendance.objects.get(
                employee=employee,
                date=today,
            )
        except Attendance.DoesNotExist:
            return Response(
                {"error": f"Hello {employee.user.first_name}, you have not checked in today."},
                status=400,
            )

        # Check current state via events
        state, last_event = _get_last_event_state(employee, today)
        if state == 'NOT_CHECKED_IN':
            return Response(
                {"error": f"Hello {employee.user.first_name}, you have not checked in today."},
                status=400,
            )
        if state == 'CHECKED_OUT':
            return Response(
                {"error": f"Hello {employee.user.first_name}, you are already checked out today."},
                status=400,
            )

        now = timezone.now()
        
        # Get effective shift for event recording
        effective_shift = employee.get_effective_shift()

        with transaction.atomic():
            AttendanceEvent.objects.create(
                employee=employee,
                shift=effective_shift,
                timestamp=now,
                event_type="CHECK_OUT",
                source="KIOSK",
            )
            attendance.recompute_from_events()

        AttendanceAuditLog.objects.create(
            event_type="CHECK_OUT",
            status="SUCCESS",
            employee=employee,
            distance=distance,
        )

        attendance.refresh_from_db()
        record_event(
            event_type="CHECK_OUT",
            category="ATTENDANCE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Kiosk attendance check-out recorded.",
            source="KIOSK",
            request=request,
            after_state=_attendance_log_state(attendance),
        )
        return Response(
            {
                "message": f"Goodbye, {employee.user.first_name}! Check-out successful.",
                "check_out": attendance.check_out,
            },
            status=200,
        )

class FaceVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        image_data = request.data.get("image")
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

        try:
            employee, distance = find_closest_match(image_data)
        except FaceExtractionError as e:
            record_event(
                event_type="FACE_VERIFY",
                category="ATTENDANCE",
                severity="WARNING",
                status="FAILED",
                actor=request.user,
                message="Face verification failed.",
                source="FACE_SERVICE",
                request=request,
                metadata={"error_type": type(e).__name__},
            )
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            record_event(
                event_type="FACE_VERIFY",
                category="ATTENDANCE",
                severity="ERROR",
                status="FAILED",
                actor=request.user,
                message="Face verification failed.",
                source="FACE_SERVICE",
                request=request,
                metadata={"error_type": type(e).__name__},
            )
            return Response({"error": "Internal server error"}, status=500)

        if not employee:
            record_event(
                event_type="FACE_VERIFY",
                category="ATTENDANCE",
                severity="WARNING",
                status="FAILED",
                actor=request.user,
                message="Face verification did not identify an employee.",
                source="FACE_SERVICE",
                request=request,
            )
            return Response({"error": "Face not recognized.", "status": "unknown"}, status=404)

        record_event(
            event_type="FACE_VERIFY",
            category="ATTENDANCE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Face verification succeeded.",
            source="FACE_SERVICE",
            request=request,
        )
        return Response(
            {
                "message": "Face verified successfully.",
                "employee_id": employee.id,
                "first_name": employee.user.first_name,
                "last_name": employee.user.last_name,
            },
            status=200,
        )


# ============================================================================
# SHIFT ASSIGNMENT VIEWS
# ============================================================================

class ShiftListView(APIView):
    """List active shifts configured for employee's employment type."""
    permission_classes = [IsEmployee]

    def get(self, request):
        employee = request.user.employee
        
        # Get shifts configured for this employee's employment type
        shifts = Shift.objects.filter(
            employment_type=employee.employment_type,
            is_active=True
        ).order_by("code")
        
        data = [
            {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "start_time": s.start_time.strftime("%H:%M"),
                "end_time": s.end_time.strftime("%H:%M"),
            }
            for s in shifts
        ]
        
        return Response({
            "shifts": data,
            "count": len(data),
            "employment_type": employee.employment_type
        })


class EmployeeShiftSelfAssignView(APIView):
    """Employee self-assigns a shift (only if no shift assigned and from their employment type)."""
    permission_classes = [IsEmployee]

    def post(self, request):
        employee = request.user.employee
        
        # Check if already has shift
        if employee.shift is not None:
            return Response(
                {"error": "You already have a shift assigned. Contact admin to change it."},
                status=400,
            )
        
        shift_id = request.data.get("shift_id")
        if not shift_id:
            return Response({"error": "shift_id is required"}, status=400)
        
        try:
            shift = Shift.objects.get(id=shift_id, is_active=True)
        except Shift.DoesNotExist:
            return Response({"error": "Invalid or inactive shift"}, status=400)
        
        # Validate shift belongs to employee's employment type
        if shift.employment_type and shift.employment_type != employee.employment_type:
            return Response(
                {"error": f"This shift is configured for {shift.employment_type} employees only"},
                status=400,
            )
        
        # Atomic check-and-set to prevent race conditions
        before_state = {"shift": None}
        with transaction.atomic():
            # Lock the employee row to prevent concurrent assignment
            employee = Employee.objects.select_for_update().get(pk=employee.pk)
            if employee.shift is not None:
                return Response(
                    {"error": "Shift already assigned by another request"},
                    status=409,
                )
            employee.shift = shift
            employee.save(update_fields=["shift"])

        record_event(
            event_type="SHIFT_ASSIGNED",
            category="ADMINISTRATION",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Employee self-assigned a shift.",
            source="API",
            request=request,
            before_state=before_state,
            after_state={"shift": _shift_log_state(shift)},
        )
        
        return Response(
            {
                "message": "Shift self-assigned successfully",
                "shift": {
                    "id": shift.id,
                    "code": shift.code,
                    "name": shift.name,
                    "start_time": shift.start_time.strftime("%H:%M"),
                    "end_time": shift.end_time.strftime("%H:%M"),
                }
            },
            status=200,
        )


class AdminEmployeeShiftAssignView(APIView):
    """Manager and Admin can assign employee shifts."""
    permission_classes = [IsManagerOrAdmin]

    def post(self, request):
        employee_email = request.data.get("employee_email")
        shift_id = request.data.get("shift_id")  # null to remove
        
        if not employee_email:
            return Response({"error": "employee_email is required"}, status=400)
        
        try:
            employee = Employee.objects.get(user__email=employee_email)
        except Employee.DoesNotExist:
            return Response({"error": "Employee not found"}, status=404)
            
        if getattr(request.user, "is_system_admin", False) and not request.user.is_superuser and not request.user.is_staff:
            from accounts.scope_service import employee_in_manager_scope
            if not employee_in_manager_scope(request.user, employee):
                return Response({"error": "You do not have permission to manage this employee's shift"}, status=403)
        
        before_state = {"shift": _shift_log_state(employee.shift)}
        shift = None
        if shift_id is not None:
            try:
                shift = Shift.objects.get(id=shift_id)
                # Admin can assign inactive shifts too
            except Shift.DoesNotExist:
                return Response({"error": "Shift not found"}, status=400)
            employee.shift = shift
            message = f"Shift '{shift.code}' assigned to {employee_email}"
        else:
            employee.shift = None
            message = f"Shift removed from {employee_email}"
        
        employee.save(update_fields=["shift"])
        record_event(
            event_type="SHIFT_ASSIGNED",
            category="ADMINISTRATION",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Employee shift assignment changed by an administrator.",
            source="ADMIN",
            request=request,
            before_state=before_state,
            after_state={"shift": _shift_log_state(shift)},
        )
        
        return Response({"message": message, "employee_email": employee_email, "shift_id": shift_id})


class AdminEmployeeShiftBulkAssignView(APIView):
    """Manager and Admin can bulk assign shifts."""
    permission_classes = [IsManagerOrAdmin]

    def post(self, request):
        shift_id = request.data.get("shift_id")
        employee_emails = request.data.get("employee_emails", [])  # list
        section = request.data.get("section")  # optional filter
        employment_type = request.data.get("employment_type")  # optional filter
        
        if shift_id is None and not employee_emails and not section and not employment_type:
            return Response({"error": "Provide shift_id and at least one target filter"}, status=400)
        
        if shift_id is not None:
            try:
                shift = Shift.objects.get(id=shift_id)
            except Shift.DoesNotExist:
                return Response({"error": "Shift not found"}, status=400)
        else:
            shift = None  # remove shift
        
        # Build queryset
        queryset = Employee.objects.filter(is_active=True)
        if getattr(request.user, "is_system_admin", False) and not request.user.is_superuser and not request.user.is_staff:
            from accounts.scope_service import filter_employees_by_manager_scope
            queryset = filter_employees_by_manager_scope(request.user, queryset)
            
        if employee_emails:
            queryset = queryset.filter(user__email__in=employee_emails)
        if section:
            queryset = queryset.filter(section=section)
        if employment_type:
            queryset = queryset.filter(employment_type=employment_type)
        employees = list(queryset.select_related("shift", "user"))
        before_state = {
            "employees": [
                {"employee_id": employee.id, "shift": _shift_log_state(employee.shift)}
                for employee in employees
            ]
        }
        count = queryset.update(shift=shift)
        after_state = {
            "employees": [
                {"employee_id": employee.id, "shift": _shift_log_state(shift)}
                for employee in employees
            ]
        }
        record_event(
            event_type="SHIFT_BULK_ASSIGNED",
            category="ADMINISTRATION",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target={"type": "employees.Employee", "label": f"{count} employees"},
            message="Bulk employee shift assignment changed.",
            source="ADMIN",
            request=request,
            before_state=before_state,
            after_state=after_state,
            metadata={"count": count},
        )
        
        action = "assigned" if shift else "removed from"
        return Response({"message": f"Shift {action} {count} employees", "count": count})


class MyShiftView(APIView):
    """Get current employee's effective shift (assigned or auto-assigned from configuration)."""
    permission_classes = [IsEmployee]

    def get(self, request):
        employee = request.user.employee
        
        # Get effective shift (assigned or single configured shift)
        effective_shift = employee.get_effective_shift()
        
        if effective_shift is None:
            # Check if there are configured shifts for this employment type
            from attendance.models import Shift
            configured_count = Shift.objects.filter(
                employment_type=employee.employment_type,
                is_active=True
            ).count()
            
            if configured_count == 0:
                return Response({
                    "shift": None, 
                    "message": "No shifts configured for your employment type",
                    "requires_configuration": True
                })
            else:
                return Response({
                    "shift": None,
                    "message": "Please select a shift",
                    "requires_selection": True,
                    "available_shifts_count": configured_count
                })
        
        shift = effective_shift
        # TimeField values may be datetime.time or string depending on DB
        def fmt_time(t):
            if hasattr(t, 'strftime'):
                return t.strftime("%H:%M")
            return str(t)
        
        return Response({
            "shift": {
                "id": shift.id,
                "code": shift.code,
                "name": shift.name,
                "start_time": fmt_time(shift.start_time),
                "end_time": fmt_time(shift.end_time),
                "is_active": shift.is_active,
            }
        })


# ============================================================================
# Employment Type Shift Configuration APIs
# ============================================================================


class AdminShiftConfigurationView(APIView):
    """Only SuperUser can configure global shifts - Manager cannot."""
    permission_classes = [IsAdminOrAppAdmin]  # Keep SuperUser/Admin only

    def get(self, request):
        """Get all shifts grouped by employment type."""
        shifts = Shift.objects.filter(is_active=True).order_by("employment_type", "code")
        
        # Group by employment type
        config = {
            "PERMANENT": [],
            "CONTRACT": [],
            "INTERN": [],
            "UNASSIGNED": []  # Legacy shifts with no employment_type
        }
        
        for shift in shifts:
            emp_type = shift.employment_type or "UNASSIGNED"
            config[emp_type].append({
                "id": shift.id,
                "code": shift.code,
                "name": shift.name,
                "start_time": shift.start_time.strftime("%H:%M"),
                "end_time": shift.end_time.strftime("%H:%M"),
            })
        
        return Response({
            "configuration": config,
            "employment_types": ["PERMANENT", "CONTRACT", "INTERN"]
        })
    
    def post(self, request):
        """Configure shifts for an employment type."""
        employment_type = request.data.get("employment_type")
        shifts_data = request.data.get("shifts", [])
        
        if not employment_type or employment_type not in ["PERMANENT", "CONTRACT", "INTERN"]:
            return Response({"error": "Valid employment_type required"}, status=400)
        
        if not isinstance(shifts_data, list):
            return Response({"error": "shifts must be an array"}, status=400)

        before_state = {
            "employment_type": employment_type,
            "shifts": [_shift_log_state(shift) for shift in Shift.objects.filter(
                employment_type=employment_type,
                is_active=True,
            )],
        }
        
        with transaction.atomic():
            # Deactivate existing shifts for this employment type
            Shift.objects.filter(employment_type=employment_type, is_active=True).update(is_active=False)
            
            # Create new shifts
            created_shifts = []
            for i, shift_data in enumerate(shifts_data):
                name = shift_data.get("name", "").strip()
                start_time = shift_data.get("start_time")
                end_time = shift_data.get("end_time")
                custom_code = shift_data.get("code", "").strip().upper()
                
                if not name:
                    return Response({"error": f"Shift {i+1}: name is required"}, status=400)
                
                try:
                    from datetime import time
                    if isinstance(start_time, str):
                        hour, minute = map(int, start_time.split(":"))
                        start_time = time(hour, minute)
                    if isinstance(end_time, str):
                        hour, minute = map(int, end_time.split(":"))
                        end_time = time(hour, minute)
                except (ValueError, AttributeError):
                    return Response({"error": f"Shift {i+1}: invalid time format (use HH:MM)"}, status=400)
                
                # Use custom code if provided, otherwise generate
                if custom_code:
                    # Check if custom code is already in use
                    if Shift.objects.filter(code=custom_code, is_active=True).exists():
                        return Response({"error": f"Shift {i+1}: code '{custom_code}' is already in use"}, status=400)
                    code = custom_code
                else:
                    # Generate unique code
                    base_code = f"{employment_type[:4]}{i+1}"
                    code = base_code
                    counter = 1
                    while Shift.objects.filter(code=code).exists():
                        code = f"{base_code}_{counter}"
                        counter += 1
                
                shift = Shift.objects.create(
                    name=name,
                    code=code,
                    start_time=start_time,
                    end_time=end_time,
                    employment_type=employment_type,
                    is_active=True,
                )
                created_shifts.append({
                    "id": shift.id,
                    "code": shift.code,
                    "name": shift.name,
                    "start_time": shift.start_time.strftime("%H:%M"),
                    "end_time": shift.end_time.strftime("%H:%M"),
                })
        
        record_event(
            event_type="SHIFT_CONFIGURATION_CHANGED",
            category="ADMINISTRATION",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target={"type": "attendance.Shift", "label": employment_type},
            message="Shift configuration changed.",
            source="ADMIN",
            request=request,
            before_state=before_state,
            after_state={"employment_type": employment_type, "shifts": created_shifts},
        )
        return Response({
            "message": f"Configured {len(created_shifts)} shifts for {employment_type}",
            "employment_type": employment_type,
            "shifts": created_shifts
        })


class AdminAllShiftsView(APIView):
    """Manager and Admin can view all shifts."""
    permission_classes = [IsManagerOrAdmin]
    
    def get(self, request):
        """Get all shifts for admin management (includes legacy shifts)."""
        shifts = Shift.objects.filter(is_active=True).order_by("employment_type", "code")
        data = []
        for shift in shifts:
            data.append({
                "id": shift.id,
                "code": shift.code,
                "name": shift.name,
                "start_time": shift.start_time.strftime("%H:%M"),
                "end_time": shift.end_time.strftime("%H:%M"),
                "employment_type": shift.employment_type or None,
            })
        return Response({"shifts": data})


# ============================================================================
# REGULARIZATION REQUEST VIEWS
# ============================================================================

class RegularizationRequestCreateView(APIView):
    """Employee creates a regularization request."""
    permission_classes = [IsEmployee]
    app_access_key = "attendance"

    def post(self, request):
        if not hasattr(request.user, "employee"):
            return Response(
                {"error": "No employee profile associated with this account."},
                status=403,
            )
        
        employee = request.user.employee

        # Grouped requests use one parent with one validated detail per date.
        if request.data.get("days") is not None:
            return self._create_period_request(request, employee)
        
        # Validate required fields
        attendance_date_str = request.data.get("attendance_date")
        request_type = request.data.get("request_type")
        reason = request.data.get("reason", "").strip()
        description = request.data.get("description", "").strip()
        requested_check_in_str = request.data.get("requested_check_in")
        requested_check_out_str = request.data.get("requested_check_out")
        
        if not all([attendance_date_str, request_type, reason]):
            return Response(
                {"error": "attendance_date, request_type, and reason are required."},
                status=400,
            )
        
        # Validate request type
        valid_types = [choice[0] for choice in RegularizationRequest.REQUEST_TYPES]
        if request_type not in valid_types:
            return Response(
                {"error": f"Invalid request_type. Must be one of: {valid_types}"},
                status=400,
            )
        
        # Parse attendance date
        try:
            from datetime import date as date_type
            attendance_date = date_type.fromisoformat(attendance_date_str)
        except ValueError:
            return Response(
                {"error": "Invalid attendance_date format. Use YYYY-MM-DD."},
                status=400,
            )
        
        # Validate 48-hour rule
        from django.utils import timezone
        import datetime as datetime_module
        now = timezone.localdate()
        max_allowed_date = now - datetime_module.timedelta(days=2)

        if attendance_date > now:
            return Response({"error": "Attendance date cannot be in the future."}, status=400)

        if attendance_date < max_allowed_date:
            return Response(
                {"error": "Regularization requests are only allowed within 48 hours of the attendance date."},
                status=400,
            )
        
        # Parse requested times if provided
        requested_check_in = None
        requested_check_out = None
        
        def parse_requested_time(value, field_name):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                raise ValueError(f"Invalid {field_name} format.")
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            if timezone.localtime(parsed).date() != attendance_date:
                raise ValueError(f"{field_name} must be on the attendance date.")
            return parsed

        if requested_check_in_str:
            try:
                requested_check_in = parse_requested_time(requested_check_in_str, "requested_check_in")
            except ValueError as exc:
                return Response(
                    {"error": str(exc)},
                    status=400,
                )
        
        if requested_check_out_str:
            try:
                requested_check_out = parse_requested_time(requested_check_out_str, "requested_check_out")
            except ValueError as exc:
                return Response(
                    {"error": str(exc)},
                    status=400,
                )

        if request_type == "FORGOT_CHECK_IN" and not requested_check_in:
            return Response({"error": "A requested check-in time is required for this request type."}, status=400)
        if request_type == "FORGOT_CHECK_OUT" and not requested_check_out:
            return Response({"error": "A requested check-out time is required for this request type."}, status=400)
        if not requested_check_in and not requested_check_out:
            return Response({"error": "At least one requested check-in or check-out time is required."}, status=400)
        
        # Validate check-out is after check-in if both provided
        if requested_check_in and requested_check_out:
            if requested_check_out <= requested_check_in:
                return Response(
                    {"error": "Requested check-out time must be after check-in time."},
                    status=400,
                )
        
        # Get existing attendance data for the date
        existing_check_in = None
        existing_check_out = None
        try:
            existing_attendance = Attendance.objects.get(employee=employee, date=attendance_date)
            existing_check_in = existing_attendance.check_in
            existing_check_out = existing_attendance.check_out
        except Attendance.DoesNotExist:
            # No existing attendance record - that's okay
            pass
        
        # Check for existing pending request on the same date
        existing_request = RegularizationRequest.objects.filter(
            employee=employee,
            attendance_date=attendance_date,
            status="PENDING"
        ).first()
        
        if existing_request:
            return Response(
                {"error": "You already have a pending regularization request for this date."},
                status=400,
            )
        
        try:
            with transaction.atomic():
                locked_employee = Employee.objects.select_for_update().get(pk=employee.pk)
                usage = regularization_quota_usage(locked_employee)
                if usage["weekly_used"] >= usage["weekly_limit"] or usage["monthly_used"] >= usage["monthly_limit"]:
                    detail = (f"You have reached the limit of {usage['weekly_limit']} regularization request(s) for this calendar week."
                              if usage["weekly_used"] >= usage["weekly_limit"] else
                              f"You have reached the limit of {usage['monthly_limit']} regularization request(s) for this calendar month.")
                    return Response({
                        "detail": detail,
                        **usage,
                    }, status=400)
                existing_request = RegularizationRequest.objects.filter(
                    employee=locked_employee, attendance_date=attendance_date, status="PENDING"
                ).first()
                if existing_request:
                    return Response({"error": "You already have a pending regularization request for this date."}, status=400)
                regularization_request = RegularizationRequest.objects.create(
                    employee=locked_employee,
                    attendance_date=attendance_date,
                    request_type=request_type,
                    existing_check_in=existing_check_in,
                    existing_check_out=existing_check_out,
                    requested_check_in=requested_check_in,
                    requested_check_out=requested_check_out,
                    reason=reason,
                    description=description,
                    status="PENDING",
                )
                message = _regularization_created_message(regularization_request)
                queue_manager_notifications_after_commit(
                    title="New regularization request",
                    message=message,
                    notification_type="REGULARIZATION",
                    email_subject="New regularization request",
                    email_body=message,
                )

            record_event(
                event_type="REGULARIZATION_CREATED",
                category="REGULARIZATION",
                severity="INFO",
                status="SUCCESS",
                actor=request.user,
                target=regularization_request,
                message="Regularization request created.",
                source="API",
                request=request,
                after_state=_regularization_log_state(regularization_request),
            )
            
            return Response({
                "message": "Regularization request submitted successfully.",
                "request_id": regularization_request.id,
                "status": regularization_request.status,
                "attendance_date": regularization_request.attendance_date,
                "request_type": regularization_request.request_type,
            }, status=201)
            
        except IntegrityError:
            return Response(
                {"error": "You already have a pending regularization request for this date."},
                status=400,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to create regularization request: {str(e)}"},
                status=500,
            )

    def _create_period_request(self, request, employee):
        import datetime as datetime_module
        from datetime import date as date_type
        from django.utils import timezone
        try:
            payload = request.data.get("days")
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            period_type = request.data.get("period_type", "DAY")
            if period_type not in {"DAY", "WEEK", "MONTH"} or not isinstance(payload, list) or not payload:
                raise ValueError("Choose a period and include at least one attendance date.")
            today = timezone.localdate()
            earliest = today - datetime_module.timedelta(days=2)
            week_start = today - datetime_module.timedelta(days=today.weekday())
            valid_types = dict(RegularizationRequest.REQUEST_TYPES)
            parsed = []
            for item in payload:
                day_date = date_type.fromisoformat(str(item.get("attendance_date", "")))
                kind, reason = item.get("request_type"), str(item.get("reason", "")).strip()
                
                if day_date > today:
                    raise ValueError(f"{day_date}: future dates are not allowed.")
                if period_type in ("WEEK", "MONTH"):
                    if day_date < week_start:
                        raise ValueError(f"{day_date}: multi-day requests are only allowed for dates in the current calendar week.")
                else:
                    if day_date < earliest:
                        raise ValueError(f"{day_date}: date must be within the past 48 hours.")
                        
                if not is_working_day(day_date):
                    day = get_day_classification(day_date)
                    reason = "weekends" if day["day_type"] == "WEEKEND" else "company holidays"
                    raise ValueError(f"{day_date}: {reason} are not eligible for regularization.")
                if kind not in valid_types or not reason: raise ValueError(f"{day_date}: request type and reason are required.")
                def parse_time(value, field):
                    if not value: return None
                    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    if timezone.is_naive(result): result = timezone.make_aware(result, timezone.get_current_timezone())
                    if timezone.localtime(result).date() != day_date: raise ValueError(f"{day_date}: {field} must fall on that date.")
                    return result
                check_in, check_out = parse_time(item.get("requested_check_in"), "check-in"), parse_time(item.get("requested_check_out"), "check-out")
                if kind == "FORGOT_CHECK_IN" and not check_in: raise ValueError(f"{day_date}: check-in is required.")
                if kind == "FORGOT_CHECK_OUT" and not check_out: raise ValueError(f"{day_date}: check-out is required.")
                if not check_in and not check_out: raise ValueError(f"{day_date}: at least one corrected time is required.")
                if check_in and check_out and check_out <= check_in: raise ValueError(f"{day_date}: check-out must be after check-in.")
                parsed.append({"date": day_date, "type": kind, "check_in": check_in, "check_out": check_out, "reason": reason, "description": str(item.get("description", "")).strip()})
            if len({row["date"] for row in parsed}) != len(parsed): raise ValueError("A date can only be included once.")
            parsed.sort(key=lambda row: row["date"])
            start, end = parsed[0]["date"], parsed[-1]["date"]
            if period_type == "DAY" and len(parsed) != 1: raise ValueError("A day request must have exactly one date.")
            if period_type == "WEEK" and any(row["date"].isocalendar()[:2] != start.isocalendar()[:2] for row in parsed): raise ValueError("Selected dates must belong to the same week.")
            if period_type == "MONTH" and any((row["date"].year, row["date"].month) != (start.year, start.month) for row in parsed): raise ValueError("Selected dates must belong to the same month.")
            selected_dates = [row["date"] for row in parsed]
            with transaction.atomic():
                locked_employee = Employee.objects.select_for_update().get(pk=employee.pk)
                usage = regularization_quota_usage(locked_employee)
                if usage["weekly_used"] >= usage["weekly_limit"] or usage["monthly_used"] >= usage["monthly_limit"]:
                    detail = (f"You have reached the limit of {usage['weekly_limit']} regularization request(s) for this calendar week."
                              if usage["weekly_used"] >= usage["weekly_limit"] else
                              f"You have reached the limit of {usage['monthly_limit']} regularization request(s) for this calendar month.")
                    return Response({
                        "detail": detail,
                        **usage,
                    }, status=400)
                has_pending = RegularizationRequest.objects.filter(employee=employee, status="PENDING", attendance_date__in=selected_dates).exists() or RegularizationRequestDay.objects.filter(request__employee=employee, request__status="PENDING", attendance_date__in=selected_dates).exists()
                if has_pending: raise ValueError("A pending request already includes one or more selected dates.")
                first = parsed[0]
                first_attendance = Attendance.objects.filter(employee=employee, date=first["date"]).first()
                parent = RegularizationRequest.objects.create(employee=employee, attendance_date=first["date"], request_type=first["type"], existing_check_in=first_attendance.check_in if first_attendance else None, existing_check_out=first_attendance.check_out if first_attendance else None, requested_check_in=first["check_in"], requested_check_out=first["check_out"], reason=first["reason"], description=first["description"], status="PENDING", period_type=period_type, period_start=start, period_end=end, attachment=str(request.data.get("attachment", "")))
                message = _regularization_created_message(parent)
                queue_manager_notifications_after_commit(
                    title="New regularization request",
                    message=message,
                    notification_type="REGULARIZATION",
                    email_subject="New regularization request",
                    email_body=message,
                )
                for row in parsed:
                    attendance = Attendance.objects.filter(employee=employee, date=row["date"]).first()
                    RegularizationRequestDay.objects.create(request=parent, attendance_date=row["date"], request_type=row["type"], existing_check_in=attendance.check_in if attendance else None, existing_check_out=attendance.check_out if attendance else None, requested_check_in=row["check_in"], requested_check_out=row["check_out"], reason=row["reason"], description=row["description"])
            record_event(
                event_type="REGULARIZATION_CREATED",
                category="REGULARIZATION",
                severity="INFO",
                status="SUCCESS",
                actor=request.user,
                target=parent,
                message="Grouped regularization request created.",
                source="API",
                request=request,
                after_state=_regularization_log_state(parent),
                metadata={"day_count": len(parsed)},
            )
            return Response({"message": "Regularization request submitted successfully.", "request_id": parent.id, "status": parent.status, "period_type": period_type, "day_count": len(parsed)}, status=201)
        except (ValueError, TypeError, KeyError) as exc:
            return Response({"error": str(exc)}, status=400)
        except IntegrityError:
            return Response({"error": "A pending request already includes one or more selected dates."}, status=400)
        except Exception as exc:
            return Response({"error": f"Failed to create regularization request: {exc}"}, status=500)


def regularization_quota_usage(employee, current_date=None):
    from datetime import datetime, date as date_type, timedelta
    from django.utils import timezone

    current_date = current_date or timezone.localdate()
    week_start = current_date - timedelta(days=current_date.weekday())
    week_end = week_start + timedelta(days=7)
    month_start = date_type(current_date.year, current_date.month, 1)
    if current_date.month == 12:
        next_month = date_type(current_date.year + 1, 1, 1)
    else:
        next_month = date_type(current_date.year, current_date.month + 1, 1)
    week_start_at = timezone.make_aware(datetime.combine(week_start, datetime.min.time()), timezone.get_current_timezone())
    week_end_at = timezone.make_aware(datetime.combine(week_end, datetime.min.time()), timezone.get_current_timezone())
    start_at = timezone.make_aware(datetime.combine(month_start, datetime.min.time()), timezone.get_current_timezone())
    end_at = timezone.make_aware(datetime.combine(next_month, datetime.min.time()), timezone.get_current_timezone())
    requests = RegularizationRequest.objects.filter(
        employee=employee,
    )
    weekly_used = requests.filter(created_at__gte=week_start_at, created_at__lt=week_end_at).count()
    monthly_used = requests.filter(created_at__gte=start_at, created_at__lt=end_at).count()
    policy = RegularizationQuotaPolicy.get_solo()
    weekly_limit, monthly_limit = policy.weekly_limit, policy.monthly_limit
    return {
        "week_start": week_start.isoformat(),
        "week_end": (week_end - timedelta(days=1)).isoformat(),
        "weekly_limit": weekly_limit,
        "weekly_used": weekly_used,
        "weekly_remaining": max(0, weekly_limit - weekly_used),
        "month": month_start.strftime("%Y-%m"),
        "monthly_limit": monthly_limit,
        "monthly_used": monthly_used,
        "monthly_remaining": max(0, monthly_limit - monthly_used),
    }


class RegularizationRequestQuotaView(APIView):
    permission_classes = [IsEmployee]
    app_access_key = "attendance"

    def get(self, request):
        if not hasattr(request.user, "employee"):
            return Response({"error": "No employee profile associated with this account."}, status=403)
        return Response(regularization_quota_usage(request.user.employee))


class RegularizationQuotaPolicyView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from .serializers import RegularizationQuotaPolicySerializer

        policy = RegularizationQuotaPolicy.get_solo()
        return Response(RegularizationQuotaPolicySerializer(policy).data)

    def patch(self, request):
        from .serializers import RegularizationQuotaPolicySerializer

        policy = RegularizationQuotaPolicy.get_solo()
        before_state = {
            "weekly_limit": policy.weekly_limit,
            "monthly_limit": policy.monthly_limit,
        }
        serializer = RegularizationQuotaPolicySerializer(
            policy,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        record_event(
            event_type="REGULARIZATION_QUOTA_CHANGED",
            category="REGULARIZATION",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=policy,
            message="Regularization quota policy changed.",
            source="ADMIN",
            request=request,
            before_state=before_state,
            after_state={
                "weekly_limit": policy.weekly_limit,
                "monthly_limit": policy.monthly_limit,
            },
        )
        return Response(serializer.data)


class RegularizationRequestListView(APIView):
    permission_classes = [IsEmployeeOrManager]
    app_access_key = "attendance"

    def get(self, request):
        manager = request.user.is_staff or request.user.is_system_admin or request.user.is_superuser
        requests = RegularizationRequest.objects.select_related("employee__user", "reviewed_by")
        if manager:
            from accounts.scope_service import filter_employees_by_manager_scope
            from employees.models import Employee
            scoped_employees = filter_employees_by_manager_scope(request.user, Employee.objects.all())
            requests = requests.filter(employee__in=scoped_employees)
            employee_id = request.query_params.get("employee_id")
            if employee_id: requests = requests.filter(employee_id=employee_id)
        elif hasattr(request.user, "employee"):
            requests = requests.filter(employee=request.user.employee)
        else:
            return Response([])
        if request.query_params.get("status"):
            requests = requests.filter(status=request.query_params["status"])
        data = []
        for req in requests.order_by("-created_at"):
            rows = list(req.days.all())
            day_rows = [{"id": row.id, "attendance_date": row.attendance_date, "request_type": row.request_type, "reason": row.reason, "description": row.description, "existing_check_in": row.existing_check_in, "existing_check_out": row.existing_check_out, "requested_check_in": row.requested_check_in, "requested_check_out": row.requested_check_out, "approved_check_in": row.approved_check_in, "approved_check_out": row.approved_check_out} for row in rows]
            if not day_rows:
                day_rows = [{"id": None, "attendance_date": req.attendance_date, "request_type": req.request_type, "reason": req.reason, "description": req.description, "existing_check_in": req.existing_check_in, "existing_check_out": req.existing_check_out, "requested_check_in": req.requested_check_in, "requested_check_out": req.requested_check_out, "approved_check_in": req.approved_check_in, "approved_check_out": req.approved_check_out}]
            first = day_rows[0]
            record = {"id": req.id, "attendance_date": req.attendance_date, "request_type": first["request_type"], "reason": first["reason"], "description": first["description"], "status": req.status, "existing_check_in": first["existing_check_in"], "existing_check_out": first["existing_check_out"], "requested_check_in": first["requested_check_in"], "requested_check_out": first["requested_check_out"], "approved_check_in": first["approved_check_in"], "approved_check_out": first["approved_check_out"], "created_at": req.created_at, "reviewed_at": req.reviewed_at, "rejection_reason": req.rejection_reason, "period_type": req.period_type, "period_start": req.period_start or req.attendance_date, "period_end": req.period_end or req.attendance_date, "attachment": req.attachment, "day_count": len(rows), "days": day_rows}
            if manager:
                record.update({"employee_id": req.employee.id, "employee_name": f"{req.employee.user.first_name} {req.employee.user.last_name}".strip(), "employee_email": req.employee.user.email})
            if req.reviewed_by: record["reviewed_by_name"] = f"{req.reviewed_by.first_name} {req.reviewed_by.last_name}".strip()
            data.append(record)
        return Response(data)


class RegularizationRequestDetailView(APIView):
    permission_classes = [IsEmployeeOrManager]
    app_access_key = "attendance"

    def get(self, request, request_id):
        manager = request.user.is_staff or request.user.is_system_admin or request.user.is_superuser
        query = RegularizationRequest.objects.select_related("employee__user", "reviewed_by", "attendance_correction")
        try:
            req = query.get(id=request_id) if manager else query.get(id=request_id, employee=request.user.employee)
        except (RegularizationRequest.DoesNotExist, AttributeError):
            return Response({"error": "Regularization request not found."}, status=404)
        if manager:
            from accounts.scope_service import employee_in_manager_scope
            if not employee_in_manager_scope(request.user, req.employee):
                return Response({"error": "You do not have permission to access this request."}, status=403)
        rows = list(req.days.all())
        days = [{"id": row.id, "attendance_date": row.attendance_date, "request_type": row.request_type, "reason": row.reason, "description": row.description, "existing_check_in": row.existing_check_in, "existing_check_out": row.existing_check_out, "requested_check_in": row.requested_check_in, "requested_check_out": row.requested_check_out, "approved_check_in": row.approved_check_in, "approved_check_out": row.approved_check_out} for row in rows]
        if not days:
            days = [{"id": None, "attendance_date": req.attendance_date, "request_type": req.request_type, "reason": req.reason, "description": req.description, "existing_check_in": req.existing_check_in, "existing_check_out": req.existing_check_out, "requested_check_in": req.requested_check_in, "requested_check_out": req.requested_check_out, "approved_check_in": req.approved_check_in, "approved_check_out": req.approved_check_out}]
        first = days[0]
        data = {"id": req.id, "employee_id": req.employee.id, "employee_name": f"{req.employee.user.first_name} {req.employee.user.last_name}".strip(), "employee_email": req.employee.user.email, **first, "status": req.status, "created_at": req.created_at, "reviewed_at": req.reviewed_at, "rejection_reason": req.rejection_reason, "is_within_48_hours": req.is_within_48_hours, "can_be_processed": req.can_be_processed, "period_type": req.period_type, "period_start": req.period_start or req.attendance_date, "period_end": req.period_end or req.attendance_date, "attachment": req.attachment, "days": days}
        if req.reviewed_by: data["reviewed_by_name"] = f"{req.reviewed_by.first_name} {req.reviewed_by.last_name}".strip()
        return Response(data)


class RegularizationRequestApproveView(APIView):
    permission_classes = [IsManagerOrAdmin]

    def post(self, request, request_id):
        try:
            with transaction.atomic():
                req = RegularizationRequest.objects.select_for_update().select_related("employee__user").get(id=request_id)
                from accounts.scope_service import employee_in_manager_scope
                if not employee_in_manager_scope(request.user, req.employee):
                    return Response({"error": "You do not have permission to access this request."}, status=403)
                before_state = _regularization_log_state(req)
                if req.status != "PENDING": return Response({"error": f"Cannot approve request with status {req.status}."}, status=400)
                if not req.is_within_48_hours: return Response({"error": "Cannot approve request outside 48-hour window."}, status=400)
                rows = list(req.days.all())
                if rows:
                    payload = request.data.get("days", [])
                    if isinstance(payload, str):
                        import json
                        payload = json.loads(payload)
                    by_id = {int(item["id"]): item for item in payload if item.get("id") is not None}
                    final = []
                    for row in rows:
                        if is_company_holiday(row.attendance_date):
                            raise ValueError(f"Cannot approve regularization for company holiday {row.attendance_date}.")
                        item = by_id.get(row.id, {})
                        def parse(field, fallback):
                            value = item.get(field, fallback)
                            if value in (None, ""): return None
                            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                            if timezone.is_naive(parsed): parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
                            if timezone.localtime(parsed).date() != row.attendance_date: raise ValueError(f"Final {field} must be on {row.attendance_date}.")
                            return parsed
                        requested_check_in = parse("check_in", row.requested_check_in)
                        requested_check_out = parse("check_out", row.requested_check_out)
                        check_in = requested_check_in or row.existing_check_in
                        check_out = requested_check_out or row.existing_check_out
                        if not check_in and not check_out: raise ValueError(f"At least one final time is required for {row.attendance_date}.")
                        if check_in and check_out and check_out <= check_in: raise ValueError(f"Check-out must be after check-in for {row.attendance_date}.")
                        final.append((row, check_in, check_out, requested_check_in, requested_check_out))
                    req.status, req.reviewed_by, req.reviewed_at = "APPROVED", request.user, timezone.now()
                    req.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
                    for row, check_in, check_out, correction_check_in, correction_check_out in final:
                        attendance, _ = Attendance.get_or_create_for_date(req.employee, row.attendance_date)
                        previous = {"check_in": attendance.check_in.isoformat() if attendance.check_in else None, "check_out": attendance.check_out.isoformat() if attendance.check_out else None, "status": attendance.status, "working_duration": str(attendance.working_duration) if attendance.working_duration else None}
                        shift = req.employee.get_effective_shift()
                        from .models import AttendanceCorrection
                        correction = AttendanceCorrection.objects.create(attendance=attendance, admin_user=request.user, correction_type="REGULARIZATION", reason=f"Regularization approved: {row.reason}", previous_data=previous)
                        for timestamp, kind in ((correction_check_in, "CHECK_IN"), (correction_check_out, "CHECK_OUT")):
                            if timestamp: AttendanceEvent.objects.create(employee=req.employee, shift=shift, timestamp=timestamp, event_type=kind, source="ADMIN", correction=correction)
                        attendance.recompute_from_events()
                        row.attendance_correction = correction
                        row.approved_check_in, row.approved_check_out = check_in, check_out
                        row.save(update_fields=["attendance_correction", "approved_check_in", "approved_check_out"])
                    _queue_regularization_outcome(req, "APPROVED")
                    record_event(
                        event_type="REGULARIZATION_APPROVED",
                        category="REGULARIZATION",
                        severity="INFO",
                        status="SUCCESS",
                        actor=request.user,
                        target=req,
                        message="Regularization request approved.",
                        source="ADMIN",
                        request=request,
                        before_state=before_state,
                        after_state=_regularization_log_state(req),
                        metadata={"approved_days": len(rows)},
                    )
                    return Response({"message": "Regularization request approved successfully.", "request_id": req.id, "status": req.status, "approved_days": len(rows)})

                def parse_legacy(field, fallback):
                    value = request.data.get(field, fallback)
                    if value in (None, ""): return None
                    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    if timezone.is_naive(parsed): parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
                    if timezone.localtime(parsed).date() != req.attendance_date: raise ValueError(f"Final {field} must be on the attendance date.")
                    return parsed
                if is_company_holiday(req.attendance_date):
                    return Response({"error": f"Cannot approve regularization for company holiday {req.attendance_date}."}, status=400)
                check_in = parse_legacy("check_in", req.requested_check_in or req.existing_check_in)
                check_out = parse_legacy("check_out", req.requested_check_out or req.existing_check_out)
                if not check_in and not check_out: return Response({"error": "At least one final check-in or check-out time is required."}, status=400)
                if check_in and check_out and check_out <= check_in: return Response({"error": "Final check-out time must be after final check-in time."}, status=400)
                correction = req.approve(request.user, approved_check_in=check_in, approved_check_out=check_out)
                _queue_regularization_outcome(req, "APPROVED")
                record_event(
                    event_type="REGULARIZATION_APPROVED",
                    category="REGULARIZATION",
                    severity="INFO",
                    status="SUCCESS",
                    actor=request.user,
                    target=req,
                    message="Regularization request approved.",
                    source="ADMIN",
                    request=request,
                    before_state=before_state,
                    after_state=_regularization_log_state(req),
                )
                return Response({"message": "Regularization request approved successfully.", "request_id": req.id, "status": req.status, "correction_id": correction.id if correction else None, "approved_check_in": req.approved_check_in, "approved_check_out": req.approved_check_out, "employee_name": f"{req.employee.user.first_name} {req.employee.user.last_name}".strip(), "attendance_date": req.attendance_date})
        except RegularizationRequest.DoesNotExist:
            return Response({"error": "Regularization request not found."}, status=404)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            return Response({"error": f"Failed to approve request: {exc}"}, status=500)


class RegularizationRequestRejectView(APIView):
    """Manager/SuperUser rejects a regularization request."""
    permission_classes = [IsManagerOrAdmin]
    
    def post(self, request, request_id):
        rejection_reason = request.data.get("rejection_reason", "").strip()
        
        if not rejection_reason:
            return Response(
                {"error": "rejection_reason is required."},
                status=400,
            )
        
        try:
            with transaction.atomic():
                regularization_request = RegularizationRequest.objects.select_for_update().select_related(
                    'employee__user'
                ).get(id=request_id)
                from accounts.scope_service import employee_in_manager_scope
                if not employee_in_manager_scope(request.user, regularization_request.employee):
                    return Response({"error": "You do not have permission to access this request."}, status=403)
                if regularization_request.status != "PENDING":
                    return Response(
                        {"error": f"Cannot reject request with status {regularization_request.status}."},
                        status=400,
                    )
                before_state = _regularization_log_state(regularization_request)
                regularization_request.reject(
                    reviewed_by_user=request.user,
                    rejection_reason=rejection_reason,
                )
                _queue_regularization_outcome(
                    regularization_request,
                    "REJECTED",
                    rejection_reason,
                )
                after_state = _regularization_log_state(regularization_request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        except RegularizationRequest.DoesNotExist:
            return Response({"error": "Regularization request not found."}, status=404)
        except Exception as e:
            return Response(
                {"error": f"Failed to reject request: {str(e)}"},
                status=500,
            )

        record_event(
            event_type="REGULARIZATION_REJECTED",
            category="REGULARIZATION",
            severity="WARNING",
            status="SUCCESS",
            actor=request.user,
            target=regularization_request,
            message="Regularization request rejected.",
            source="ADMIN",
            request=request,
            before_state=before_state,
            after_state=after_state,
        )

        return Response({
            "message": "Regularization request rejected.",
            "request_id": regularization_request.id,
            "status": regularization_request.status,
            "rejection_reason": regularization_request.rejection_reason,
            "employee_name": f"{regularization_request.employee.user.first_name} {regularization_request.employee.user.last_name}",
            "attendance_date": regularization_request.attendance_date,
        })

class OfficeLocationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        locations = OfficeLocation.objects.all().order_by("-is_active", "name")
        from .serializers import OfficeLocationSerializer

        serializer = OfficeLocationSerializer(locations, many=True)
        return Response(serializer.data, status=200)

    def post(self, request):
        if not (
            request.user.is_superuser
            or request.user.is_staff
            or getattr(request.user, "is_system_admin", False)
        ):
            return Response({"error": "Only Superadmin can manage office locations."}, status=403)

        from .serializers import OfficeLocationSerializer

        serializer = OfficeLocationSerializer(data=request.data)
        if serializer.is_valid():
            location = serializer.save()
            record_event(
                event_type="OFFICE_LOCATION_CREATED",
                category="ADMINISTRATION",
                severity="INFO",
                status="SUCCESS",
                actor=request.user,
                target=location,
                message="Office location created.",
                source="ADMIN",
                request=request,
                after_state=_location_log_state(location),
            )
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class OfficeLocationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        if not (
            request.user.is_superuser
            or request.user.is_staff
            or getattr(request.user, "is_system_admin", False)
        ):
            return Response({"error": "Only Superadmin can manage office locations."}, status=403)

        try:
            location = OfficeLocation.objects.get(pk=pk)
        except OfficeLocation.DoesNotExist:
            return Response({"error": "Office location not found."}, status=404)

        from .serializers import OfficeLocationSerializer

        serializer = OfficeLocationSerializer(location, data=request.data, partial=True)
        if serializer.is_valid():
            before_state = _location_log_state(location)
            location = serializer.save()
            record_event(
                event_type="OFFICE_LOCATION_UPDATED",
                category="ADMINISTRATION",
                severity="INFO",
                status="SUCCESS",
                actor=request.user,
                target=location,
                message="Office location updated.",
                source="ADMIN",
                request=request,
                before_state=before_state,
                after_state=_location_log_state(location),
            )
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        if not (
            request.user.is_superuser
            or request.user.is_staff
            or getattr(request.user, "is_system_admin", False)
        ):
            return Response({"error": "Only Superadmin can manage office locations."}, status=403)

        try:
            location = OfficeLocation.objects.get(pk=pk)
        except OfficeLocation.DoesNotExist:
            return Response({"error": "Office location not found."}, status=404)

        before_state = _location_log_state(location)
        location.delete()
        record_event(
            event_type="OFFICE_LOCATION_DELETED",
            category="ADMINISTRATION",
            severity="WARNING",
            status="SUCCESS",
            actor=request.user,
            target={
                "type": "attendance.OfficeLocation",
                "id": location.pk,
                "label": before_state["name"],
            },
            message="Office location deleted.",
            source="ADMIN",
            request=request,
            before_state=before_state,
            after_state=None,
        )
        return Response({"message": "Office location deleted successfully."}, status=200)
