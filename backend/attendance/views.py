from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from employees.models import Employee
from .models import Attendance, AttendanceAuditLog
from .face_service import find_closest_match, FaceExtractionError


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

        if attendance.status == "LEAVE":
            status = "LEAVE"
        elif attendance.check_out is not None:
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


class WebsiteFacialCheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = request.user.employee
        today = timezone.localdate()

        image_data = request.data.get("image")
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

        # 1. Verify face
        try:
            recognized_employee, distance = find_closest_match(image_data)
        except FaceExtractionError as e:
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            return Response({"error": "Internal server error"}, status=500)

        if not recognized_employee:
            return Response({"error": "We couldn't verify your identity."}, status=403)

        # 2. Enforce website security: recognized employee must match authenticated user
        if recognized_employee.id != employee.id:
            return Response({"error": "Recognized face does not match your authenticated account."}, status=403)

        # 3. Apply existing attendance rules
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

class WebsiteFacialCheckOutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = request.user.employee
        today = timezone.localdate()

        image_data = request.data.get("image")
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

        # 1. Verify face
        try:
            recognized_employee, distance = find_closest_match(image_data)
        except FaceExtractionError as e:
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            return Response({"error": "Internal server error"}, status=500)

        if not recognized_employee:
            return Response({"error": "We couldn't verify your identity."}, status=403)

        # 2. Enforce website security
        if recognized_employee.id != employee.id:
            return Response({"error": "Recognized face does not match your authenticated account."}, status=403)

        # 3. Apply existing attendance checkout rules
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
        attendance, created = Attendance.objects.get_or_create(
            employee=employee,
            date=today,
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
                {"error": f"Hello {employee.user.first_name}, you cannot check in because you are on approved leave today."},
                status=400,
            )

        if not created and attendance.check_in is not None:
            return Response(
                {"error": f"Hello {employee.user.first_name}, you are already checked in today."},
                status=400,
            )

        attendance.check_in = timezone.now()
        attendance.status = "INCOMPLETE"
        attendance.save()

        AttendanceAuditLog.objects.create(
            event_type="CHECK_IN",
            status="SUCCESS",
            employee=employee,
            distance=distance,
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

        if attendance.check_in is None:
            return Response(
                {"error": f"Hello {employee.user.first_name}, you have not checked in today."},
                status=400,
            )

        if attendance.check_out is not None:
            return Response(
                {"error": f"Hello {employee.user.first_name}, you are already checked out today."},
                status=400,
            )

        cooldown_seconds = 300
        time_since_check_in = (timezone.now() - attendance.check_in).total_seconds()
        if time_since_check_in < cooldown_seconds:
            remaining = int(cooldown_seconds - time_since_check_in)
            return Response(
                {
                    "error": f"Safety Cooldown: Please wait {remaining} more seconds before checking out.",
                },
                status=400,
            )

        attendance.check_out = timezone.now()
        attendance.working_duration = (
            attendance.check_out - attendance.check_in
        )
        attendance.status = "PRESENT"
        attendance.save()

        AttendanceAuditLog.objects.create(
            event_type="CHECK_OUT",
            status="SUCCESS",
            employee=employee,
            distance=distance,
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