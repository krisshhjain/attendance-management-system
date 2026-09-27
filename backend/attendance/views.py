from django.utils import timezone
from django.db import transaction
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
)

from employees.models import Employee
from .models import Attendance, AttendanceEvent, AttendanceAuditLog, Shift
from .geofence import validate_attendance_geofence
from .face_service import find_closest_match, verify_employee_face, FaceExtractionError
from leave_management.models import LeaveRequest


def _get_last_event_state(employee, date):
    """Determine check-in/check-out state from events or attendance record.
    Returns: (state, last_event) where state is:
      - 'CHECKED_IN'   : currently checked in (has CHECK_IN, no CHECK_OUT)
      - 'CHECKED_OUT'  : already checked out (has CHECK_OUT)
      - 'NOT_CHECKED_IN' : no check-in today
    """
    last_event = employee.attendance_events.filter(
        timestamp__date=date
    ).order_by("-timestamp").first()

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

        if attendance.status == "LEAVE":
            return Response(
                {"error": "You cannot check in because you are on approved leave today."},
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
        working_day = is_working_day(today)

        try:
            attendance = Attendance.objects.get(
                employee=employee,
                date=today,
            )
        except Attendance.DoesNotExist:
            # Always return NOT_CHECKED_IN - weekends should allow attendance if employee comes to office
            return Response({
                "status": "NOT_CHECKED_IN",
                "check_in": None,
                "check_out": None,
                "working_duration": None,
                "is_working_day": working_day,
            })

        working_duration = attendance.working_duration
        state, last_event = _get_last_event_state(employee, today)

        if attendance.check_in and not attendance.check_out:
            working_duration = timezone.now() - attendance.check_in

        if attendance.status == "LEAVE":
            status = "LEAVE"
        elif state == "NOT_CHECKED_IN":
            # Always allow check-in, even on weekends
            status = "NOT_CHECKED_IN"
        elif state == "CHECKED_OUT":
            status = "COMPLETED"
        else:
            status = "CHECKED_IN"

        return Response({
            "status": status,
            "check_in": attendance.check_in,
            "check_out": attendance.check_out,
            "working_duration": working_duration,
            "is_working_day": working_day,
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
        is_weekend = today.weekday() in [5, 6]

        for emp in teammates:
            att = attendance_map.get(emp.id)
            full_name = f"{emp.user.first_name} {emp.user.last_name}".strip() or emp.user.email

            if emp.id in on_leave_ids:
                member_status = "ON_LEAVE"
                on_leave_count += 1
            elif att is not None and att.check_in is not None:
                member_status = "CHECKED_IN"
                checked_in_count += 1
            elif is_weekend:
                # Weekend with no attendance → not counted as yet-to-check-in
                member_status = "WEEKEND"
            else:
                member_status = "YET_TO_CHECK_IN"
                yet_to_check_in_count += 1

            member_data = {
                "id": emp.id,
                "name": full_name,
                "department": emp.department,
                "subsection": emp.subsection,
                "status": member_status,
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
        if request.user.is_staff or request.user.is_system_admin:
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
            # Managers/admins see all employees' attendance
            # Check for employee_id filter
            employee_id = request.query_params.get('employee_id')
            if employee_id:
                try:
                    attendance_records = Attendance.objects.filter(
                        employee_id=employee_id
                    ).select_related('employee__user').order_by("-date")
                except ValueError:
                    return Response({"error": "Invalid employee_id"}, status=400)
            else:
                # Return all employees' attendance
                attendance_records = Attendance.objects.select_related(
                    'employee__user'
                ).order_by("-date")
        else:
            # Regular employees see only their own attendance
            if not hasattr(request.user, "employee"):
                return Response([])
            employee = request.user.employee
            attendance_records = Attendance.objects.filter(
                employee=employee
            ).order_by("-date")

        data = []
        for attendance in attendance_records:
            record = {
                "date": attendance.date,
                "status": attendance.status,
                "check_in": attendance.check_in,
                "check_out": attendance.check_out,
                "working_duration": attendance.working_duration,
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
        attendance_records = Attendance.objects.filter(date=filter_date).select_related("employee")
        attendance_map = {att.employee_id: att for att in attendance_records}

        data = []
        for emp in employees:
            att = attendance_map.get(emp.id)
            
            # Determine actual display status
            if att:
                if att.status == "LEAVE":
                    status_display = "LEAVE"
                elif att.check_in is None:
                    status_display = "ABSENT"
                else:
                    status_display = att.status # PRESENT or INCOMPLETE
            else:
                status_display = "ABSENT"
                
            data.append({
                "employee": emp.user.email,
                "employee_name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
                "section": emp.section,
                "subsection": emp.subsection,
                "date": filter_date,
                "status": status_display,
                "check_in": att.check_in if att else None,
                "check_out": att.check_out if att else None,
                "working_duration": str(att.working_duration) if att and att.working_duration else None,
            })

        # Sort: Present first, then Incomplete, then Absent/Leave
        data.sort(key=lambda x: (
            0 if x["status"] == "PRESENT" else 1 if x["status"] == "INCOMPLETE" else 2,
            x["employee_name"]
        ))
        
        return Response(data)


from config.business_rules import is_working_day

class AdminDashboardView(APIView):
    """Manager and Admin can view dashboard."""
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        today = timezone.localdate()

        total_employees = Employee.objects.count()
        active_employees = Employee.objects.filter(is_active=True).count()

        today_attendance = Attendance.objects.filter(date=today)

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
        now = timezone.now()
        attendance_data = []
        for attendance in attendance_records:
            working_duration = attendance.working_duration
            if attendance.check_in and not attendance.check_out:
                working_duration = now - attendance.check_in
            attendance_data.append({
                "employee": attendance.employee.user.email,
                "section": attendance.employee.section,
                "subsection": attendance.employee.subsection,
                "date": attendance.date,
                "status": attendance.status,
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
            "is_working_day": is_working_day(today),
        })

class AdminResetAttendanceView(APIView):
    """Only SuperUser can reset attendance - Manager cannot."""
    permission_classes = [IsAdminUser]  # Keep SuperUser-only

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

        return Response({"message": "Attendance successfully reset for today."})

class AdminEditAttendanceView(APIView):
    """Manager and Admin can edit past attendance."""
    permission_classes = [IsManagerOrAdmin]

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

        if check_in_str:
            try:
                attendance.check_in = datetime.fromisoformat(check_in_str.replace('Z', '+00:00'))
            except ValueError:
                return Response({"error": "Invalid check_in time format"}, status=400)
        else:
            attendance.check_in = None

        if check_out_str:
            try:
                attendance.check_out = datetime.fromisoformat(check_out_str.replace('Z', '+00:00'))
            except ValueError:
                return Response({"error": "Invalid check_out time format"}, status=400)
        else:
            attendance.check_out = None

        if attendance.check_in and attendance.check_out:
            attendance.working_duration = attendance.check_out - attendance.check_in
            # Auto-correct status to PRESENT if both times are provided
            if status == "INCOMPLETE":
                attendance.status = "PRESENT"
            else:
                attendance.status = status
        else:
            attendance.working_duration = None
            # If only check-in or no times, keep the provided status
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

        base_query = Attendance.objects.filter(
            date=target_date, 
            check_in__isnull=False, 
            check_out__isnull=True
        )

        if is_all:
            attendances = base_query
        elif employee_email:
            attendances = base_query.filter(employee__user__email=employee_email)
            if not attendances.exists():
                return Response({"error": "No active check-in found for this employee on this date"}, status=404)
        else:
            return Response({"error": "Must provide 'all': true or 'employee': email"}, status=400)

        count = 0
        now = timezone.now()
        for att in attendances:
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
            count += 1
            
        return Response({"message": f"Successfully forced check-out for {count} records", "count": count})
class WebsiteFacialCheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = request.user.employee
        today = timezone.localdate()

        image_data = request.data.get("image")
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

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
            is_match, distance = verify_employee_face(employee, image_data)
        except FaceExtractionError as e:
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            return Response({"error": "Internal server error"}, status=500)

        if not is_match:
            return Response({"error": "Recognized face does not match your authenticated account."}, status=403)

        # Get or create attendance record
        attendance, created = Attendance.get_or_create_for_date(employee, today)

        if attendance.status == "LEAVE":
            return Response(
                {"error": "You cannot check in because you are on approved leave today."},
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

        image_data = request.data.get("image")
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

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
            is_match, distance = verify_employee_face(employee, image_data)
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
        image_data = request.data.get("image")
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

        try:
            employee, distance = find_closest_match(image_data)
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
        image_data = request.data.get("image")
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

        try:
            employee, distance = find_closest_match(image_data)
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
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            return Response({"error": "Internal server error"}, status=500)

        if not employee:
            return Response({"error": "Face not recognized.", "status": "unknown"}, status=404)

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
        if employee_emails:
            queryset = queryset.filter(user__email__in=employee_emails)
        if section:
            queryset = queryset.filter(section=section)
        if employment_type:
            queryset = queryset.filter(employment_type=employment_type)
        
        count = queryset.update(shift=shift)
        
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
