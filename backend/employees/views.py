from copy import deepcopy

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAdminUser, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Employee, FaceProfile
from .serializers import EmployeeCreateSerializer, EmployeeListSerializer, EmployeeUpdateSerializer
from attendance.face_service import process_enrollment, FaceExtractionError
from leave_management.permissions import IsManagerOrSuperUser
from system_logs.services import record_event


def _employee_log_state(employee):
    return {
        "user_id": employee.user_id,
        "email": employee.user.email,
        "first_name": employee.user.first_name,
        "last_name": employee.user.last_name,
        "department": employee.department,
        "employment_type": employee.employment_type,
        "date_joined": employee.date_joined.isoformat(),
        "is_active": employee.is_active,
        "section": employee.section,
        "subsection": employee.subsection,
        "app_access": deepcopy(employee.app_access),
    }


def _manager_log_state(user):
    return {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_system_admin": user.is_system_admin,
        "is_superuser": user.is_superuser,
        "hr_copilot_sections": deepcopy(user.hr_copilot_sections),
        "hr_copilot_subsections": deepcopy(user.hr_copilot_subsections),
    }


class IsAdminOrManager(BasePermission):
    """Allow access to admin users or managers."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            (request.user.is_staff or request.user.is_system_admin)
        )


class EmployeeCreateView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request):
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee = serializer.save()
        record_event(
            event_type="EMPLOYEE_CREATED",
            category="EMPLOYEE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Employee account created.",
            source="API",
            request=request,
            after_state=_employee_log_state(employee),
        )

        return Response(
            {
                "id": employee.id,
                "email": employee.user.email,
                "first_name": employee.user.first_name,
                "last_name": employee.user.last_name,
                "department": employee.department,
                "employment_type": employee.employment_type,
                "date_joined": employee.date_joined,
                "is_active": employee.is_active,
                "section": employee.section,
                "subsection": employee.subsection,
            },
            status=status.HTTP_201_CREATED,
        )


class EmployeeListView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        employees = Employee.objects.select_related("user", "shift").order_by("id")
        serializer = EmployeeListSerializer(employees, many=True)
        return Response(serializer.data)


class EmployeeDetailView(APIView):
    permission_classes = [IsManagerOrSuperUser]

    def get_object(self, pk):
        try:
            return Employee.objects.select_related("user").get(pk=pk)
        except Employee.DoesNotExist:
            return None

    def get(self, request, pk):
        employee = self.get_object(pk)
        if not employee:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = EmployeeListSerializer(employee)
        return Response(serializer.data)

    @transaction.atomic
    def patch(self, request, pk):
        employee = self.get_object(pk)
        if not employee:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EmployeeUpdateSerializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        before_state = _employee_log_state(employee)
        before_active = employee.is_active
        before_access = deepcopy(employee.app_access)
        updated = serializer.save()
        after_state = _employee_log_state(updated)

        if before_active != updated.is_active:
            record_event(
                event_type=(
                    "EMPLOYEE_ACTIVATED"
                    if updated.is_active
                    else "EMPLOYEE_DEACTIVATED"
                ),
                category="EMPLOYEE",
                severity="INFO",
                status="SUCCESS",
                actor=request.user,
                target=updated,
                message="Employee activation status changed.",
                source="API",
                request=request,
                before_state=before_state,
                after_state=after_state,
            )

        if before_active == updated.is_active or before_state != after_state:
            if before_active == updated.is_active:
                record_event(
                    event_type="EMPLOYEE_UPDATED",
                    category="EMPLOYEE",
                    severity="INFO",
                    status="SUCCESS",
                    actor=request.user,
                    target=updated,
                    message="Employee account updated.",
                    source="API",
                    request=request,
                    before_state=before_state,
                    after_state=after_state,
                )
            elif any(
                before_state[field] != after_state[field]
                for field in before_state
                if field != "is_active"
            ):
                record_event(
                    event_type="EMPLOYEE_UPDATED",
                    category="EMPLOYEE",
                    severity="INFO",
                    status="SUCCESS",
                    actor=request.user,
                    target=updated,
                    message="Employee account updated.",
                    source="API",
                    request=request,
                    before_state=before_state,
                    after_state=after_state,
                )

        if before_access != updated.app_access:
            record_event(
                event_type="ACCESS_CHANGED",
                category="EMPLOYEE",
                severity="INFO",
                status="SUCCESS",
                actor=request.user,
                target=updated,
                message="Employee application access changed.",
                source="API",
                request=request,
                before_state={"app_access": before_access},
                after_state={"app_access": deepcopy(updated.app_access)},
            )

        return Response(EmployeeListSerializer(updated).data)

    @transaction.atomic
    def delete(self, request, pk):
        employee = self.get_object(pk)
        if not employee:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        user = employee.user
        employee.delete()
        user.delete()

        return Response({"message": "Employee deleted successfully."}, status=status.HTTP_200_OK)


class AdminEmployeePasswordChangeView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, pk):
        try:
            employee = Employee.objects.select_related("user").get(pk=pk)
        except Employee.DoesNotExist:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        new_password = request.data.get("new_password")
        if not new_password:
            return Response({"error": "new_password is required."}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 8:
            return Response({"error": "Password must be at least 8 characters long."}, status=status.HTTP_400_BAD_REQUEST)

        user = employee.user
        user.set_password(new_password)
        user.save()

        employee.must_change_password = True
        employee.save(update_fields=["must_change_password"])
        record_event(
            event_type="EMPLOYEE_PASSWORD_CHANGED",
            category="EMPLOYEE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=employee,
            message="Employee password changed by an administrator.",
            source="API",
            request=request,
            after_state={"must_change_password": employee.must_change_password},
        )

        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)


class EmployeeFaceEnrollmentView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, pk):
        try:
            employee = Employee.objects.get(pk=pk)
        except Employee.DoesNotExist:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        images = request.data.getlist("images") if hasattr(request.data, "getlist") else request.data.get("images", [])
        
        if len(images) != 3:
            record_event(
                event_type="FACE_ENROLLMENT",
                category="EMPLOYEE",
                severity="WARNING",
                status="FAILED",
                actor=request.user,
                target=employee,
                message="Face enrollment failed validation.",
                source="API",
                request=request,
            )
            return Response({"error": "Exactly 3 images are required for enrollment."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Process images and extract template
            # If images are files from multipart form data, read their content
            image_bytes = []
            for img in images:
                if hasattr(img, 'read'):
                    image_bytes.append(img.read())
                else:
                    image_bytes.append(img)
            
            template = process_enrollment(image_bytes)
            
            # Save template
            FaceProfile.objects.update_or_create(
                employee=employee,
                defaults={
                    "face_template": template,
                    "status": "ACTIVE",
                    "model_name": "ArcFace",
                    "detector_backend": "retinaface",
                    "version": "1.0"
                }
            )
            record_event(
                event_type="FACE_ENROLLMENT",
                category="EMPLOYEE",
                severity="INFO",
                status="SUCCESS",
                actor=request.user,
                target=employee,
                message="Employee face enrollment completed.",
                source="API",
                request=request,
                after_state={"face_profile_status": "ACTIVE"},
            )
            
            return Response({"message": "Face enrolled successfully."}, status=status.HTTP_200_OK)
            
        except FaceExtractionError as e:
            record_event(
                event_type="FACE_ENROLLMENT",
                category="EMPLOYEE",
                severity="WARNING",
                status="FAILED",
                actor=request.user,
                target=employee,
                message="Face enrollment failed.",
                source="API",
                request=request,
                metadata={"error_type": type(e).__name__},
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            record_event(
                event_type="FACE_ENROLLMENT",
                category="EMPLOYEE",
                severity="ERROR",
                status="FAILED",
                actor=request.user,
                target=employee,
                message="Face enrollment failed.",
                source="API",
                request=request,
                metadata={"error_type": type(e).__name__},
            )
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# Manager Management (SuperUser only)
# ============================================================================

class ManagerCreateView(APIView):
    """SuperUser can create Manager accounts."""
    permission_classes = [IsAdminUser]  # SuperUser only

    @transaction.atomic
    def post(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        email = request.data.get("email", "").strip()
        password = request.data.get("password", "")
        first_name = request.data.get("first_name", "").strip()
        last_name = request.data.get("last_name", "").strip()
        hr_copilot_sections = request.data.get("hr_copilot_sections", [])
        hr_copilot_subsections = request.data.get("hr_copilot_subsections", [])
        
        # Validation
        if not email:
            return Response({"error": "Email is required"}, status=400)
        if not password:
            return Response({"error": "Password is required"}, status=400)
        if len(password) < 8:
            return Response({"error": "Password must be at least 8 characters"}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({"error": "User with this email already exists"}, status=400)
        
        # Create Manager user
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_system_admin=True,  # Mark as Manager
            is_staff=False,
            is_superuser=False,
        )
        
        user.hr_copilot_sections = hr_copilot_sections
        user.hr_copilot_subsections = hr_copilot_subsections
        user.save()
        record_event(
            event_type="MANAGER_CREATED",
            category="EMPLOYEE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=user,
            message="Manager account created.",
            source="API",
            request=request,
            after_state=_manager_log_state(user),
        )
        record_event(
            event_type="ROLE_CHANGED",
            category="EMPLOYEE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=user,
            message="Manager role established.",
            source="API",
            request=request,
            before_state={"is_system_admin": False, "is_superuser": False},
            after_state={"is_system_admin": True, "is_superuser": False},
        )
        
        return Response({
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_system_admin": user.is_system_admin,
            "hr_copilot_sections": user.hr_copilot_sections,
            "hr_copilot_subsections": user.hr_copilot_subsections,
        }, status=201)


class ManagerListView(APIView):
    """SuperUser can list all Managers."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        managers = User.objects.filter(
            is_system_admin=True,
            is_superuser=False
        ).order_by("id")
        
        data = [{
            "id": m.id,
            "email": m.email,
            "first_name": m.first_name,
            "last_name": m.last_name,
            "is_active": m.is_active,
            "hr_copilot_sections": m.hr_copilot_sections,
            "hr_copilot_subsections": m.hr_copilot_subsections,
        } for m in managers]
        
        return Response(data)


class ManagerDetailView(APIView):
    """SuperUser can view/update/delete Manager accounts."""
    permission_classes = [IsAdminUser]

    def get_object(self, pk):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.get(pk=pk, is_system_admin=True, is_superuser=False)
        except User.DoesNotExist:
            return None

    def get(self, request, pk):
        manager = self.get_object(pk)
        if not manager:
            return Response({"error": "Manager not found"}, status=404)
        
        return Response({
            "id": manager.id,
            "email": manager.email,
            "first_name": manager.first_name,
            "last_name": manager.last_name,
            "is_active": manager.is_active,
            "hr_copilot_sections": manager.hr_copilot_sections,
            "hr_copilot_subsections": manager.hr_copilot_subsections,
        })

    @transaction.atomic
    def patch(self, request, pk):
        manager = self.get_object(pk)
        if not manager:
            return Response({"error": "Manager not found"}, status=404)
        before_state = _manager_log_state(manager)
        before_active = manager.is_active

        # Update allowed fields
        if "first_name" in request.data:
            manager.first_name = request.data["first_name"].strip()
        if "last_name" in request.data:
            manager.last_name = request.data["last_name"].strip()
        if "is_active" in request.data:
            manager.is_active = request.data["is_active"]
        if "hr_copilot_sections" in request.data:
            manager.hr_copilot_sections = request.data["hr_copilot_sections"]
        if "hr_copilot_subsections" in request.data:
            manager.hr_copilot_subsections = request.data["hr_copilot_subsections"]
        manager.save()
        after_state = _manager_log_state(manager)

        if before_active != manager.is_active:
            record_event(
                event_type=("MANAGER_ACTIVATED" if manager.is_active else "MANAGER_DEACTIVATED"),
                category="EMPLOYEE",
                severity="INFO",
                status="SUCCESS",
                actor=request.user,
                target=manager,
                message="Manager activation status changed.",
                source="API",
                request=request,
                before_state=before_state,
                after_state=after_state,
            )
        if before_state != after_state and (
            before_active == manager.is_active
            or any(
                before_state[field] != after_state[field]
                for field in before_state
                if field != "is_active"
            )
        ):
            record_event(
                event_type="MANAGER_UPDATED",
                category="EMPLOYEE",
                severity="INFO",
                status="SUCCESS",
                actor=request.user,
                target=manager,
                message="Manager account updated.",
                source="API",
                request=request,
                before_state=before_state,
                after_state=after_state,
            )
        
        return Response({
            "id": manager.id,
            "email": manager.email,
            "first_name": manager.first_name,
            "last_name": manager.last_name,
            "is_active": manager.is_active,
            "hr_copilot_sections": manager.hr_copilot_sections,
            "hr_copilot_subsections": manager.hr_copilot_subsections,
        })

    @transaction.atomic
    def delete(self, request, pk):
        manager = self.get_object(pk)
        if not manager:
            return Response({"error": "Manager not found"}, status=404)
        
        manager.delete()
        return Response({"message": "Manager deleted successfully"})


class ManagerPasswordChangeView(APIView):
    """SuperUser can change Manager password."""
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, pk):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            manager = User.objects.get(pk=pk, is_system_admin=True, is_superuser=False)
        except User.DoesNotExist:
            return Response({"error": "Manager not found"}, status=404)
        
        new_password = request.data.get("new_password")
        if not new_password:
            return Response({"error": "new_password is required"}, status=400)
        if len(new_password) < 8:
            return Response({"error": "Password must be at least 8 characters"}, status=400)
        
        manager.set_password(new_password)
        manager.save()
        record_event(
            event_type="MANAGER_PASSWORD_CHANGED",
            category="EMPLOYEE",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=manager,
            message="Manager password changed by an administrator.",
            source="API",
            request=request,
        )
        
        return Response({"message": "Manager password changed successfully"})
