from celery import shared_task

from attendance.models import AttendanceEvent
from notifications.models import Notification


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

    employee_user = event.employee.user
    action = event.event_type
    employee_name = employee_user.get_full_name().strip() or employee_user.email

    _, created = Notification.objects.get_or_create(
        attendance_event=event,
        defaults={
            "user": employee_user,
            "title": f"Attendance {action.replace('_', ' ').title()}",
            "message": f"{employee_name} recorded a {action} attendance event.",
            "notification_type": "ATTENDANCE",
            "is_read": False,
        },
    )

    return "created" if created else "already_exists"
