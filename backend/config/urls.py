"""
Root URL routing configuration for the Attendance Management System.

Defines top-level routing for:
- Built-in Django administrative portal (`admin/`)
- User authentication and JWT endpoints (`api/auth/`)
- Attendance recording and reporting (`api/attendance/`)
- Administrative attendance, employee, and metric dashboards (`api/admin/`)
- Employee leave management and approval workflows (`api/leave/`)

Also provides local development serving for uploaded media assets when DEBUG is True.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView
from attendance.views import AdminDashboardView


urlpatterns = [
    # Django built-in administration site
    path("admin/", admin.site.urls),

    # Authentication endpoints: login, token refresh, password changes, profile
    path("api/auth/", include("accounts.urls")),

    # Explicit JWT token refresh endpoint alias matching frontend standard SimpleJWT paths
    # (also accessible via api/auth/refresh/ inside accounts.urls)
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # Employee attendance check-in, check-out, and personal history
    path("api/attendance/", include("attendance.urls")),

    # Administrative attendance operations (records, logs, overrides)
    path("api/admin/", include("attendance.admin_urls")),

    # Administrative employee CRUD, lifecycle, and profile management
    path("api/admin/employees/", include("employees.urls")),

    # Aggregated administrative attendance metrics and KPI summaries
    path("api/admin/dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),

    # Employee leave applications, balances, and supervisor approval flows
    path("api/leave/", include("leave_management.urls")),
]

# In local development mode, serve media uploads directly via Django.
# In production, web servers (e.g. Nginx) or cloud object storage should serve MEDIA_ROOT.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
