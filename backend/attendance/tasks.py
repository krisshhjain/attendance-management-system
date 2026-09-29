from datetime import date, timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from attendance.models import Attendance, AttendanceEvent
from config.business_rules import is_working_day
from employees.models import Employee
from leave_management.models import LeaveRequest
from notifications.services import (
    active_manager_users,
    queue_deduplicated_notification_after_commit,
    get_or_create_notification,
)


def _is_regularization_correction(event):
    from attendance.models import RegularizationRequest, RegularizationRequestDay

    return (
        RegularizationRequest.objects.filter(
            employee=event.employee,
            status="APPROVED",
        )
        .filter(
            Q(approved_check_in=event.timestamp)
            | Q(approved_check_out=event.timestamp)
        )
        .exists()
        or RegularizationRequestDay.objects.filter(
            request__employee=event.employee,
            request__status="APPROVED",
        )
        .filter(
            Q(approved_check_in=event.timestamp)
            | Q(approved_check_out=event.timestamp)
        )
        .exists()
    )


@shared_task
def test_celery_task(message):
    print(f"[Celery Test Task] {message}")
    return message


@shared_task
def create_attendance_notification(attendance_event_id):
    try:
        event = AttendanceEvent.objects.select_related("employee__user").get(
            pk=attendance_event_id
        )
    except AttendanceEvent.DoesNotExist:
        return "event_not_found"

    if event.source == "ADMIN" and _is_regularization_correction(event):
        return "regularization_correction_skipped"

    employee_user = event.employee.user
    action = event.event_type
    employee_name = employee_user.get_full_name().strip() or employee_user.email

    _, created = get_or_create_notification(
        user=employee_user,
        attendance_event=event,
        title=f"Attendance {action.replace('_', ' ').title()}",
        message=f"{employee_name} recorded a {action} attendance event.",
        notification_type="ATTENDANCE",
    )

    return "created" if created else "already_exists"


def _has_valid_attendance(employee, target_date):
    return Attendance.objects.filter(
        employee=employee,
        date=target_date,
        check_in__isnull=False,
    ).exists()


def _has_approved_leave(employee, target_date):
    return LeaveRequest.objects.filter(
        employee=employee,
        status="APPROVED",
        start_date__lte=target_date,
        end_date__gte=target_date,
    ).exists()


@shared_task(name="attendance.check_consecutive_absences")
def check_consecutive_absences(run_date=None):
    """Alert managers about absence on the two most recent required days."""
    if run_date:
        if isinstance(run_date, str):
            evaluation_date = date.fromisoformat(run_date)
        else:
            evaluation_date = run_date
    else:
        evaluation_date = timezone.localdate()

    required_dates = []
    candidate_date = evaluation_date - timedelta(days=1)
    while len(required_dates) < 2:
        if is_working_day(candidate_date):
            required_dates.append(candidate_date)
        candidate_date -= timedelta(days=1)

    first_absence_date, second_absence_date = required_dates

    managers = list(active_manager_users())
    alerts_created = 0

    with transaction.atomic():
        employees = Employee.objects.select_related("user").filter(
            is_active=True,
            user__is_active=True,
        )
        for employee in employees:
            absent_on_first = not _has_valid_attendance(employee, first_absence_date)
            absent_on_second = not _has_valid_attendance(employee, second_absence_date)
            on_leave = _has_approved_leave(employee, first_absence_date) or _has_approved_leave(
                employee, second_absence_date
            )

            if not (absent_on_first and absent_on_second and not on_leave):
                continue

            employee_name = employee.user.get_full_name().strip() or employee.user.email
            date_label = f"{second_absence_date} and {first_absence_date}"
            title = "Employee Absent for 2 Consecutive Working Days"
            message = f"{employee_name} has been absent on {date_label}."
            subject = "Attendance alert: 2 consecutive absences"
            deduplication_prefix = (
                f"ABSENCE_ALERT:{employee.pk}:{second_absence_date}:{first_absence_date}"
            )

            for manager in managers:
                before = manager.notifications.filter(
                    deduplication_key=f"{deduplication_prefix}:{manager.pk}"
                ).exists()
                queue_deduplicated_notification_after_commit(
                    user=manager,
                    title=title,
                    message=message,
                    notification_type="ABSENCE_ALERT",
                    deduplication_key=f"{deduplication_prefix}:{manager.pk}",
                    email_subject=subject,
                    email_body=(
                        f"{employee_name} has been absent on {date_label}. "
                        "Please review this attendance alert."
                    ),
                )
                if not before:
                    alerts_created += 1

    return {
        "evaluated": True,
        "first_absence_date": str(second_absence_date),
        "second_absence_date": str(first_absence_date),
        "alerts_created": alerts_created,
    }
