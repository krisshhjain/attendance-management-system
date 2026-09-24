from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Employee, FaceProfile
from .serializers import EmployeeCreateSerializer, EmployeeListSerializer, EmployeeUpdateSerializer
from attendance.face_service import process_enrollment, FaceExtractionError


class EmployeeCreateView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request):
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee = serializer.save()

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
    permission_classes = [IsAdminUser]

    def get(self, request):
        employees = Employee.objects.select_related("user").order_by("id")
        serializer = EmployeeListSerializer(employees, many=True)
        return Response(serializer.data)


class EmployeeDetailView(APIView):
    permission_classes = [IsAdminUser]

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
        updated = serializer.save()

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
            
            return Response({"message": "Face enrolled successfully."}, status=status.HTTP_200_OK)
            
        except FaceExtractionError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)