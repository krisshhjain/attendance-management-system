from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Notification
from .tasks import send_notification_email
from system_logs.services import record_event


NOTIFICATION_TYPES = {
    "ATTENDANCE",
    "LEAVE",
    "REGULARIZATION",
    "ABSENCE_ALERT",
    "SYSTEM",
}


def create_notification(
    *,
    user,
    title,
    message,
    notification_type="SYSTEM",
    attendance_event=None,
    deduplication_key=None,
):
    """Create one notification through the shared notification boundary."""
    if notification_type not in NOTIFICATION_TYPES:
        raise ValueError(f"Unsupported notification type: {notification_type}")

    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        attendance_event=attendance_event,
        deduplication_key=deduplication_key,
    )
    record_event(
        event_type="NOTIFICATION_CREATED",
        category="NOTIFICATION",
        severity="INFO",
        status="SUCCESS",
        actor="SYSTEM",
        target=notification,
        message="Notification created.",
        source="SYSTEM",
        after_state={
            "notification_type": notification.notification_type,
            "is_read": notification.is_read,
            "attendance_event_id": notification.attendance_event_id,
        },
    )
    return notification


def get_or_create_notification(
    *,
    user,
    title,
    message,
    notification_type="SYSTEM",
    attendance_event=None,
    deduplication_key=None,
):
    if notification_type not in NOTIFICATION_TYPES:
        raise ValueError(f"Unsupported notification type: {notification_type}")

    lookup = {"deduplication_key": deduplication_key} if deduplication_key else {
        "user": user,
        "attendance_event": attendance_event,
    }
    notification, created = Notification.objects.get_or_create(
        **lookup,
        defaults={
            "user": user,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "attendance_event": attendance_event,
            "deduplication_key": deduplication_key,
            "is_read": False,
        },
    )
    if created:
        record_event(
            event_type="NOTIFICATION_CREATED",
            category="NOTIFICATION",
            severity="INFO",
            status="SUCCESS",
            actor="SYSTEM",
            target=notification,
            message="Notification created.",
            source="SYSTEM",
            after_state={
                "notification_type": notification.notification_type,
                "is_read": notification.is_read,
                "attendance_event_id": notification.attendance_event_id,
            },
        )
    return notification, created


def queue_deduplicated_notification_after_commit(
    *,
    user,
    title,
    message,
    notification_type,
    deduplication_key,
    email_subject=None,
    email_body=None,
):
    """Publish one idempotent notification and email after its transaction commits."""
    def publish():
        _, created = get_or_create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            deduplication_key=deduplication_key,
        )
        if created and email_subject and email_body and user.email:
            record_event(
                event_type="EMAIL_QUEUED",
                category="NOTIFICATION",
                severity="INFO",
                status="PENDING",
                actor="SYSTEM",
                target=user,
                message="Notification email queued.",
                source="CELERY",
                metadata={"recipient_count": 1},
            )
            send_notification_email.delay([user.email], email_subject, email_body)

    transaction.on_commit(publish)


def queue_notification_after_commit(
    *,
    user,
    title,
    message,
    notification_type,
    email_subject=None,
    email_body=None,
):
    """Create an in-app notification and optionally enqueue its email after commit."""
    def publish():
        create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
        )
        if email_subject and email_body and user.email:
            record_event(
                event_type="EMAIL_QUEUED",
                category="NOTIFICATION",
                severity="INFO",
                status="PENDING",
                actor="SYSTEM",
                target=user,
                message="Notification email queued.",
                source="CELERY",
                metadata={"recipient_count": 1},
            )
            send_notification_email.delay(
                [user.email],
                email_subject,
                email_body,
            )

    transaction.on_commit(publish)


def active_manager_users():
    """Temporary recipient strategy: every active application Manager."""
    User = get_user_model()
    return User.objects.filter(
        is_active=True,
        is_system_admin=True,
        is_superuser=False,
    ).order_by("pk")


def queue_manager_notifications_after_commit(
    *, title, message, notification_type, email_subject=None, email_body=None
):
    for manager in active_manager_users():
        queue_notification_after_commit(
            user=manager,
            title=title,
            message=message,
            notification_type=notification_type,
            email_subject=email_subject,
            email_body=email_body,
        )
