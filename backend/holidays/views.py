from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from leave_management.permissions import IsSuperAdmin

from .models import Holiday
from .serializers import HolidaySerializer


class ActiveHolidayListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = HolidaySerializer

    def get_queryset(self):
        return Holiday.objects.filter(is_active=True).order_by("date")


class HolidayAdminListCreateView(ListCreateAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = HolidaySerializer
    queryset = Holiday.objects.all().order_by("date")


class HolidayAdminDetailView(RetrieveUpdateAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = HolidaySerializer
    queryset = Holiday.objects.all()
    http_method_names = ["get", "put", "patch", "head", "options"]
