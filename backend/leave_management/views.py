import os
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.models import Employee
from .models import LeavePolicy, LeaveRequest, LeaveType
from .permissions import (
    IsAdminOrSuperAdmin,
    IsEmployee,
    IsSystemAdminOrSuperAdminReadOnly,
)
from .serializers import (
    CreateLeaveRequestSerializer,
    LeavePolicySerializer,
    LeaveRequestSerializer,
    LeaveTypeSerializer,
)
from .services import (
    approve_leave_request,
    calculate_employee_leave_balances,
    calculate_working_days,
    cancel_leave_request,
    deny_leave_request,
    validate_leave_request,
)


# ==============================================================================
# EMPLOYEE VIEWS
# ==============================================================================

class EmployeeLeaveTypesView(APIView):
    permission_classes = [IsEmployee]

    def get(self, request):
        types = LeaveType.objects.filter(is_active=True).order_by("name")
        serializer = LeaveTypeSerializer(types, many=True)
        return Response(serializer.data)


class EmployeeLeaveBalancesView(APIView):
    permission_classes = [IsEmployee]

    def get(self, request):
        employee = request.user.employee
        year = request.query_params.get("year")
        try:
            year = int(year) if year else None
        except ValueError:
            return Response({"error": "Invalid year parameter."}, status=400)

        balances = calculate_employee_leave_balances(employee, year=year)
        return Response(balances)


class EstimateLeaveDurationView(APIView):
    permission_classes = [IsEmployee]

    def post(self, request):
        start_date_str = request.data.get("start_date")
        end_date_str = request.data.get("end_date")
        day_type = request.data.get("day_type", "FULL_DAY")

        if not start_date_str or not end_date_str:
            return Response({"error": "start_date and end_date are required."}, status=400)

        from datetime import date as date_type
        try:
            start_date = date_type.fromisoformat(start_date_str)
            end_date = date_type.fromisoformat(end_date_str)
        except ValueError:
            return Response({"error": "Invalid date format. Expected YYYY-MM-DD."}, status=400)

        duration = calculate_working_days(start_date, end_date, day_type)
        return Response({"duration_days": float(duration)})


class EmployeeLeaveRequestsView(APIView):
    permission_classes = [IsEmployee]

    def get(self, request):
        employee = request.user.employee
        status_filter = request.query_params.get("status")

        requests = LeaveRequest.objects.filter(employee=employee).select_related(
            "leave_type", "reviewed_by", "cancelled_by"
        )
        if status_filter:
            requests = requests.filter(status=status_filter.upper())

        requests = requests.order_by("-submitted_at")
        serializer = LeaveRequestSerializer(requests, many=True)
        return Response(serializer.data)

    def post(self, request):
        employee = request.user.employee
        serializer = CreateLeaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        leave_type = serializer.validated_data["leave_type"]
        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]
        day_type = serializer.validated_data.get("day_type", "FULL_DAY")
        reason = serializer.validated_data.get("reason", "")
        attachment = serializer.validated_data.get("attachment", "")

        try:
            duration = validate_leave_request(
                employee=employee,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                day_type=day_type,
                reason=reason,
                attachment=attachment,
            )
        except ValidationError as e:
            return Response({"error": e.message if hasattr(e, "message") else str(e.messages[0] if hasattr(e, "messages") else e)}, status=400)

        leave_req = LeaveRequest.objects.create(
            employee=employee,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            day_type=day_type,
            duration_days=duration,
            reason=reason,
            attachment=attachment,
            status="PENDING",
        )

        return Response(
            LeaveRequestSerializer(leave_req).data,
            status=status.HTTP_201_CREATED,
        )


class EmployeeLeaveRequestDetailView(APIView):
    permission_classes = [IsEmployee]

    def get(self, request, pk):
        try:
            leave_req = LeaveRequest.objects.select_related(
                "employee", "leave_type", "reviewed_by", "cancelled_by"
            ).get(pk=pk, employee=request.user.employee)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        return Response(LeaveRequestSerializer(leave_req).data)


class EmployeeCancelLeaveRequestView(APIView):
    permission_classes = [IsEmployee]

    def post(self, request, pk):
        try:
            leave_req = LeaveRequest.objects.get(pk=pk, employee=request.user.employee)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        try:
            updated_req = cancel_leave_request(leave_req, user=request.user)
        except ValidationError as e:
            return Response({"error": e.message if hasattr(e, "message") else str(e)}, status=400)

        return Response(LeaveRequestSerializer(updated_req).data)


# ==============================================================================
# ADMIN VIEWS
# ==============================================================================

class AdminLeaveRequestsView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        requests = LeaveRequest.objects.select_related(
            "employee", "employee__user", "leave_type", "reviewed_by", "cancelled_by"
        )

        status_param = request.query_params.get("status")
        if status_param:
            requests = requests.filter(status=status_param.upper())

        employee_id = request.query_params.get("employee_id")
        if employee_id:
            requests = requests.filter(employee_id=employee_id)

        requests = requests.order_by("-submitted_at")
        serializer = LeaveRequestSerializer(requests, many=True)
        return Response(serializer.data)


class AdminLeaveRequestDetailView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request, pk):
        try:
            leave_req = LeaveRequest.objects.select_related(
                "employee", "employee__user", "leave_type", "reviewed_by", "cancelled_by"
            ).get(pk=pk)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        return Response(LeaveRequestSerializer(leave_req).data)


class AdminApproveLeaveView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, pk):
        try:
            leave_req = LeaveRequest.objects.get(pk=pk)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        remarks = request.data.get("remarks", "")
        try:
            approved_req = approve_leave_request(
                leave_request=leave_req,
                reviewer_user=request.user,
                remarks=remarks,
            )
        except ValidationError as e:
            return Response({"error": e.message if hasattr(e, "message") else str(e)}, status=400)

        return Response(LeaveRequestSerializer(approved_req).data)


class AdminDenyLeaveView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, pk):
        try:
            leave_req = LeaveRequest.objects.get(pk=pk)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        remarks = request.data.get("remarks", "")
        try:
            denied_req = deny_leave_request(
                leave_request=leave_req,
                reviewer_user=request.user,
                remarks=remarks,
            )
        except ValidationError as e:
            return Response({"error": e.message if hasattr(e, "message") else str(e)}, status=400)

        return Response(LeaveRequestSerializer(denied_req).data)


class AdminCancelApprovedLeaveView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, pk):
        try:
            leave_req = LeaveRequest.objects.get(pk=pk)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        try:
            cancelled_req = cancel_leave_request(
                leave_request=leave_req,
                user=request.user,
            )
        except ValidationError as e:
            return Response({"error": e.message if hasattr(e, "message") else str(e)}, status=400)

        return Response(LeaveRequestSerializer(cancelled_req).data)


class AdminEmployeeLeaveBalancesView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        employee_id = request.query_params.get("employee_id")
        year = request.query_params.get("year")
        try:
            year = int(year) if year else None
        except ValueError:
            return Response({"error": "Invalid year."}, status=400)

        if employee_id:
            try:
                emp = Employee.objects.select_related("user").get(pk=employee_id)
            except Employee.DoesNotExist:
                return Response({"error": "Employee not found."}, status=404)

            balances = calculate_employee_leave_balances(emp, year=year)
            return Response({
                "employee_id": emp.id,
                "employee_email": emp.user.email,
                "employment_type": emp.employment_type,
                "balances": balances,
            })
        else:
            employees = Employee.objects.filter(is_active=True).select_related("user")
            result = []
            for emp in employees:
                balances = calculate_employee_leave_balances(emp, year=year)
                result.append({
                    "employee_id": emp.id,
                    "employee_email": emp.user.email,
                    "employment_type": emp.employment_type,
                    "balances": balances,
                })
            return Response(result)


# ==============================================================================
# SUPER ADMIN VIEWS
# ==============================================================================

class SuperAdminLeaveTypesListCreateView(APIView):
    permission_classes = [IsSystemAdminOrSuperAdminReadOnly]

    def get(self, request):
        types = LeaveType.objects.all().order_by("name")
        serializer = LeaveTypeSerializer(types, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = LeaveTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lt = serializer.save()
        return Response(LeaveTypeSerializer(lt).data, status=status.HTTP_201_CREATED)


class SuperAdminLeaveTypeDetailView(APIView):
    permission_classes = [IsSystemAdminOrSuperAdminReadOnly]

    def get_object(self, pk):
        try:
            return LeaveType.objects.get(pk=pk)
        except LeaveType.DoesNotExist:
            return None

    def get(self, request, pk):
        lt = self.get_object(pk)
        if not lt:
            return Response({"error": "Leave type not found."}, status=404)
        return Response(LeaveTypeSerializer(lt).data)

    def patch(self, request, pk):
        lt = self.get_object(pk)
        if not lt:
            return Response({"error": "Leave type not found."}, status=404)
        serializer = LeaveTypeSerializer(lt, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(LeaveTypeSerializer(updated).data)

    def delete(self, request, pk):
        lt = self.get_object(pk)
        if not lt:
            return Response({"error": "Leave type not found."}, status=404)
        lt.is_active = False
        lt.save()
        return Response({"message": "Leave type deactivated successfully."})


class SuperAdminLeavePoliciesListCreateView(APIView):
    permission_classes = [IsSystemAdminOrSuperAdminReadOnly]

    def get(self, request):
        policies = LeavePolicy.objects.select_related("leave_type").all().order_by("-effective_from", "employee_type")
        serializer = LeavePolicySerializer(policies, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = LeavePolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = serializer.save()
        return Response(LeavePolicySerializer(policy).data, status=status.HTTP_201_CREATED)


class SuperAdminLeavePolicyDetailView(APIView):
    permission_classes = [IsSystemAdminOrSuperAdminReadOnly]

    def get_object(self, pk):
        try:
            return LeavePolicy.objects.select_related("leave_type").get(pk=pk)
        except LeavePolicy.DoesNotExist:
            return None

    def get(self, request, pk):
        policy = self.get_object(pk)
        if not policy:
            return Response({"error": "Leave policy not found."}, status=404)
        return Response(LeavePolicySerializer(policy).data)

    def patch(self, request, pk):
        policy = self.get_object(pk)
        if not policy:
            return Response({"error": "Leave policy not found."}, status=404)
        serializer = LeavePolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(LeavePolicySerializer(updated).data)

    def delete(self, request, pk):
        policy = self.get_object(pk)
        if not policy:
            return Response({"error": "Leave policy not found."}, status=404)
        policy.is_active = False
        policy.save()
        return Response({"message": "Leave policy deactivated successfully."})


class FileUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response({"error": "No file provided."}, status=400)

        file = request.FILES['file']
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024
        if file.size > max_size:
            return Response({"error": "File size exceeds 5MB limit."}, status=400)

        # Validate file extension
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
        file_extension = os.path.splitext(file.name)[1].lower()
        if file_extension not in allowed_extensions:
            return Response({
                "error": f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
            }, status=400)

        try:
            # Save file with unique name
            import uuid
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = f"leave_attachments/{unique_filename}"
            
            saved_path = default_storage.save(file_path, file)
            file_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
            
            return Response({
                "message": "File uploaded successfully.",
                "file_url": file_url,
                "file_path": saved_path,
                "original_name": file.name
            })
            
        except Exception as e:
            return Response({"error": "Failed to upload file."}, status=500)
