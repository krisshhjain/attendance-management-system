import csv
import io
import json
from datetime import datetime, time, timedelta
from html import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth import get_user_model
from django.http import HttpResponse, StreamingHttpResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from leave_management.permissions import IsSuperAdmin

from .models import SystemLog
from .serializers import SystemLogSerializer


CATEGORIES = {
    "AUTHENTICATION",
    "EMPLOYEE",
    "ATTENDANCE",
    "REGULARIZATION",
    "LEAVE",
    "ADMINISTRATION",
    "NOTIFICATION",
    "HR_COPILOT",
    "CELERY",
    "SECURITY",
}
EVENT_TYPES = {
    "LOGIN_SUCCESS",
    "LOGIN_FAILED",
    "PASSWORD_CHANGED",
    "UNAUTHORIZED_ACCESS",
    "FORBIDDEN_ACCESS",
    "EMPLOYEE_CREATED",
    "EMPLOYEE_UPDATED",
    "EMPLOYEE_ACTIVATED",
    "EMPLOYEE_DEACTIVATED",
    "EMPLOYEE_PASSWORD_CHANGED",
    "FACE_ENROLLMENT",
    "MANAGER_CREATED",
    "MANAGER_UPDATED",
    "MANAGER_ACTIVATED",
    "MANAGER_DEACTIVATED",
    "MANAGER_PASSWORD_CHANGED",
    "ACCESS_CHANGED",
    "ROLE_CHANGED",
    "CHECK_IN",
    "CHECK_OUT",
    "FACE_VERIFY",
    "ADMIN_FORCE_CHECKOUT",
    "ATTENDANCE_RESET",
    "ATTENDANCE_EDIT",
    "ABSENCE_DETECTED",
    "REGULARIZATION_CREATED",
    "REGULARIZATION_SUBMITTED",
    "REGULARIZATION_APPROVED",
    "REGULARIZATION_REJECTED",
    "REGULARIZATION_QUOTA_CHANGED",
    "SHIFT_ASSIGNED",
    "SHIFT_BULK_ASSIGNED",
    "SHIFT_CONFIGURATION_CHANGED",
    "OFFICE_LOCATION_CREATED",
    "OFFICE_LOCATION_UPDATED",
    "OFFICE_LOCATION_DELETED",
    "LEAVE_CREATED",
    "LEAVE_UPDATED",
    "LEAVE_APPROVED",
    "LEAVE_DENIED",
    "LEAVE_CANCELLED",
    "LEAVE_TYPE_CREATED",
    "LEAVE_TYPE_UPDATED",
    "LEAVE_TYPE_DELETED",
    "LEAVE_POLICY_CREATED",
    "LEAVE_POLICY_UPDATED",
    "LEAVE_POLICY_DELETED",
    "NOTIFICATION_CREATED",
    "NOTIFICATION_READ",
    "NOTIFICATION_DELETED",
    "EMAIL_QUEUED",
    "EMAIL_SENT",
    "EMAIL_FAILED",
    "EMAIL_RETRY",
    "COPILOT_CONVERSATION",
    "COPILOT_QUERY_FAILED",
    "COPILOT_ACTION_REQUESTED",
    "COPILOT_ACTION_CONFIRMED",
    "COPILOT_ACTION_EXECUTED",
    "COPILOT_ACTION_FAILED",
    "COPILOT_ACTION_CANCELLED",
    "COPILOT_ACTION_EXPIRED",
    "TASK_STARTED",
    "TASK_SUCCESS",
    "TASK_FAILED",
    "TASK_RETRY",
}
SEVERITIES = {value for value, _ in SystemLog.SEVERITY_CHOICES}
STATUSES = {value for value, _ in SystemLog.STATUS_CHOICES}
ACTOR_ROLES = {"EMPLOYEE", "MANAGER", "STAFF", "SUPERUSER", "USER", "SYSTEM", "ANONYMOUS"}
SOURCES = {
    "API",
    "ADMIN",
    "MOBILE",
    "KIOSK",
    "FACE_WEB",
    "FACE_SERVICE",
    "CELERY",
    "SYSTEM",
    "HR_COPILOT",
}
ORDERING = {"timestamp", "-timestamp", "created_at", "-created_at", "id", "-id"}
EXPORT_HEADERS = [
    "id", "timestamp", "severity", "category", "event_type", "status",
    "actor", "actor_role", "target_type", "target_id", "target_label",
    "message", "source", "ip_address", "user_agent", "request_id",
    "before_state", "after_state", "metadata",
]


class SystemLogPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class SystemLogListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        try:
            queryset = self._filtered_queryset(request)
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)

        paginator = SystemLogPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = SystemLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def _filtered_queryset(self, request):
        params = request.query_params
        queryset = SystemLog.objects.select_related("actor").all()

        search = params.get("search", "").strip()
        if len(search) > 200:
            raise ValueError("search must be 200 characters or fewer.")
        if search:
            queryset = queryset.filter(
                Q(actor__email__icontains=search)
                | Q(actor__first_name__icontains=search)
                | Q(actor__last_name__icontains=search)
                | Q(target_type__icontains=search)
                | Q(target_id__icontains=search)
                | Q(target_label__icontains=search)
                | Q(event_type__icontains=search)
                | Q(category__icontains=search)
                | Q(severity__icontains=search)
                | Q(status__icontains=search)
                | Q(source__icontains=search)
                | Q(message__icontains=search)
                | Q(request_id__icontains=search)
            )

        queryset = self._exact_filter(queryset, params, "category", CATEGORIES)
        queryset = self._exact_filter(queryset, params, "event_type", EVENT_TYPES)
        queryset = self._exact_filter(queryset, params, "severity", SEVERITIES)
        queryset = self._exact_filter(queryset, params, "status", STATUSES)
        queryset = self._exact_filter(queryset, params, "source", SOURCES)
        queryset = self._exact_filter(queryset, params, "actor_role", ACTOR_ROLES)

        actor = params.get("actor")
        if actor:
            try:
                actor_id = int(actor)
            except (TypeError, ValueError):
                raise ValueError("actor must be a positive integer.")
            if actor_id <= 0:
                raise ValueError("actor must be a positive integer.")
            queryset = queryset.filter(actor_id=actor_id)

        date_from = self._parse_date(params.get("date_from"), "date_from")
        date_to = self._parse_date(params.get("date_to"), "date_to")
        if date_from and date_to and date_from > date_to:
            raise ValueError("date_from cannot be later than date_to.")
        if date_from:
            queryset = queryset.filter(timestamp__gte=self._start_of_day(date_from))
        if date_to:
            queryset = queryset.filter(timestamp__lt=self._start_of_day(date_to + timedelta(days=1)))

        ordering = params.get("ordering", "-timestamp")
        ordering_fields = [field.strip() for field in ordering.split(",") if field.strip()]
        if not ordering_fields or any(field not in ORDERING for field in ordering_fields):
            raise ValueError("ordering contains an unsupported field.")
        if "id" not in {field.lstrip("-") for field in ordering_fields}:
            ordering_fields.append("-id")

        page = params.get("page")
        if page:
            try:
                if int(page) < 1:
                    raise ValueError
            except (TypeError, ValueError):
                raise ValueError("page must be a positive integer.")
        page_size = params.get("page_size")
        if page_size:
            try:
                page_size_value = int(page_size)
            except (TypeError, ValueError):
                raise ValueError("page_size must be an integer between 1 and 100.")
            if not 1 <= page_size_value <= 100:
                raise ValueError("page_size must be between 1 and 100.")

        return queryset.order_by(*ordering_fields)

    @staticmethod
    def _exact_filter(queryset, params, name, allowed):
        value = params.get(name)
        if value:
            if value not in allowed:
                raise ValueError(f"Invalid {name}.")
            queryset = queryset.filter(**{name: value})
            return queryset
        return queryset

    @staticmethod
    def _parse_date(value, name):
        if not value:
            return None
        parsed = parse_date(value)
        if parsed is None:
            raise ValueError(f"{name} must use YYYY-MM-DD format.")
        return parsed

    @staticmethod
    def _start_of_day(value):
        return timezone.make_aware(datetime.combine(value, time.min), timezone.get_current_timezone())


class SystemLogDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request, pk):
        log = get_object_or_404(SystemLog.objects.select_related("actor"), pk=pk)
        return Response(SystemLogSerializer(log).data)


class SystemLogActorView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        search = request.query_params.get("search", "").strip()
        if len(search) > 100:
            return Response({"detail": "search must be 100 characters or fewer."}, status=400)
        users = get_user_model().objects.all().order_by("email")
        if search:
            user_filter = (
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
            if search.isdigit():
                user_filter |= Q(id=int(search))
            users = users.filter(user_filter)
        return Response([
            {
                "id": user.id,
                "email": user.email,
                "name": user.get_full_name().strip() or user.email,
            }
            for user in users[:20]
        ])


class SystemLogExportView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        export_format = request.query_params.get("export_format", "csv").lower()
        if export_format not in {"csv", "xlsx"}:
            return Response({"detail": "format must be csv or xlsx."}, status=400)
        try:
            queryset = SystemLogListView()._filtered_queryset(request)
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)

        if export_format == "xlsx":
            return self._xlsx_response(queryset)
        return self._csv_response(queryset)

    @staticmethod
    def _serialized_row(log):
        data = SystemLogSerializer(log).data
        actor = data.get("actor") or {}
        data["actor"] = actor.get("email") or actor.get("name") or ""
        for field in ("before_state", "after_state", "metadata"):
            data[field] = json.dumps(data[field], ensure_ascii=True, sort_keys=True) if data[field] else ""
        return [data.get(header, "") for header in EXPORT_HEADERS]

    def _csv_response(self, queryset):
        def rows():
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(EXPORT_HEADERS)
            yield output.getvalue()
            for log in queryset.iterator(chunk_size=500):
                output.seek(0)
                output.truncate(0)
                writer.writerow(self._serialized_row(log))
                yield output.getvalue()

        response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="system-logs.csv"'
        return response

    def _xlsx_response(self, queryset):
        output = io.BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
            )
            archive.writestr(
                "_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
            )
            archive.writestr(
                "xl/workbook.xml",
                '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="System Logs" sheetId="1" r:id="rId1"/></sheets></workbook>',
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
            )
            with archive.open("xl/worksheets/sheet1.xml", "w") as sheet:
                sheet.write(b'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>')
                for row_number, row in enumerate(self._iter_xlsx_rows(queryset), start=1):
                    sheet.write(f'<row r="{row_number}">'.encode())
                    for column, value in enumerate(row, start=1):
                        cell_ref = f"{_xlsx_column(column)}{row_number}"
                        safe_value = _excel_safe_string(value)
                        sheet.write(f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(safe_value)}</t></is></c>'.encode())
                    sheet.write(b"</row>")
                sheet.write(b"</sheetData></worksheet>")

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="system-logs.xlsx"'
        return response

    def _iter_xlsx_rows(self, queryset):
        yield EXPORT_HEADERS
        for log in queryset.iterator(chunk_size=500):
            yield self._serialized_row(log)


def _xlsx_column(number):
    value = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _excel_safe_string(value):
    value = str(value or "")
    return f"'{value}" if value[:1] in {"=", "+", "-", "@"} else value
