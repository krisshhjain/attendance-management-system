from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from employees.models import Employee
from .models import Attendance


class CheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = request.user.employee
        today = timezone.localdate()

        attendance, created = Attendance.objects.get_or_create(
            employee=employee,
            date=today,
        )

        if attendance.status == "LEAVE":
            return Response(
                {"error": "You cannot check in because you are on approved leave today."},
                status=400,
            )

        from leave_management.models import LeaveRequest
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

        if not created and attendance.check_in is not None:
            return Response(
                {"error": "Already checked in today"},
                status=400,
            )

        attendance.check_in = timezone.now()
        attendance.status = "INCOMPLETE"
        attendance.save()

        return Response(
            {
                "message": "Check-in successful",
                "check_in": attendance.check_in,
            },
            status=201,
        )

class CheckOutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = request.user.employee
        today = timezone.localdate()

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

        if attendance.check_in is None:
            return Response(
                {"error": "You have not checked in today"},
                status=400,
            )

        if attendance.check_out is not None:
            return Response(
                {"error": "Already checked out today"},
                status=400,
            )

        # Safety 5-minute rest period check
        cooldown_seconds = 300
        time_since_check_in = (timezone.now() - attendance.check_in).total_seconds()
        if time_since_check_in < cooldown_seconds:
            remaining = int(cooldown_seconds - time_since_check_in)
            mins = remaining // 60
            secs = remaining % 60
            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            return Response(
                {
                    "error": f"Safety Cooldown: You must wait 5 minutes after checking in before checking out. Please wait {time_str} longer.",
                    "cooldown_remaining_seconds": remaining,
                },
                status=400,
            )

        attendance.check_out = timezone.now()
        attendance.working_duration = (
            attendance.check_out - attendance.check_in
        )
        attendance.status = "PRESENT"
        attendance.save()

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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = request.user.employee
        today = timezone.localdate()

        try:
            attendance = Attendance.objects.get(
                employee=employee,
                date=today,
            )
        except Attendance.DoesNotExist:
            return Response({
                "status": "NOT_CHECKED_IN",
                "check_in": None,
                "check_out": None,
                "working_duration": None,
            })

        if attendance.check_out is not None:
            status = "COMPLETED"
        else:
            status = "CHECKED_IN"

        return Response({
            "status": status,
            "check_in": attendance.check_in,
            "check_out": attendance.check_out,
            "working_duration": attendance.working_duration,
        })

class AttendanceHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = request.user.employee

        attendance_records = Attendance.objects.filter(
            employee=employee
        ).order_by("-date")

        data = []

        for attendance in attendance_records:
            data.append({
                "date": attendance.date,
                "status": attendance.status,
                "check_in": attendance.check_in,
                "check_out": attendance.check_out,
                "working_duration": attendance.working_duration,
            })

        return Response(data)

class AdminAttendanceView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        attendance_records = Attendance.objects.select_related(
            "employee",
            "employee__user",
        )

        # Optional date filter: ?date=YYYY-MM-DD
        date_param = request.query_params.get("date")
        if date_param:
            from datetime import date as date_type
            try:
                filter_date = date_type.fromisoformat(date_param)
            except ValueError:
                return Response(
                    {"error": f"Invalid date '{date_param}'. Expected format: YYYY-MM-DD."},
                    status=400,
                )
            attendance_records = attendance_records.filter(date=filter_date)

        attendance_records = attendance_records.order_by("-date", "-check_in")

        data = []

        for attendance in attendance_records:
            data.append({
                "employee": attendance.employee.user.email,
                "section": attendance.employee.section,
                "subsection": attendance.employee.subsection,
                "date": attendance.date,
                "status": attendance.status,
                "check_in": attendance.check_in,
                "check_out": attendance.check_out,
                "working_duration": str(attendance.working_duration) if attendance.working_duration else None,
            })

        return Response(data)


class AdminDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.localdate()

        total_employees = Employee.objects.count()
        active_employees = Employee.objects.filter(is_active=True).count()

        today_attendance = Attendance.objects.filter(date=today)

        present_today = today_attendance.filter(
            status="PRESENT"
        ).count()

        checked_in_today = today_attendance.filter(
            check_in__isnull=False,
            check_out__isnull=True,
        ).count()

        completed_today = today_attendance.filter(
            check_in__isnull=False,
            check_out__isnull=False,
        ).count()

        return Response({
            "total_employees": total_employees,
            "active_employees": active_employees,
            "present_today": present_today,
            "checked_in_today": checked_in_today,
            "completed_today": completed_today,
        })

class AdminForceCheckoutView(APIView):
    permission_classes = [IsAdminUser]

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
            att.check_out = now
            att.working_duration = now - att.check_in
            att.status = "PRESENT"
            att.save()
            count += 1
            
        return Response({"message": f"Successfully forced check-out for {count} records", "count": count})