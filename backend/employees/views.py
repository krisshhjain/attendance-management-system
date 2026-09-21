from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Employee
from .serializers import EmployeeCreateSerializer, EmployeeListSerializer, EmployeeUpdateSerializer


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