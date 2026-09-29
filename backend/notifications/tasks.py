import logging

from celery import shared_task
from django.core.mail import send_mail
from system_logs.services import record_event


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, name="notifications.send_notification_email")
def send_notification_email(self, recipient_list, subject, body):
    """Send notification email asynchronously with bounded transient retries."""
    task_id = getattr(self.request, "id", "")
    task_metadata = {
        "task_name": self.name,
        "task_id": task_id,
        "retry_count": self.request.retries,
        "recipient_count": len(recipient_list),
    }
    record_event(
        event_type="TASK_STARTED",
        category="CELERY",
        severity="INFO",
        status="PENDING",
        actor="SYSTEM",
        message="Notification email task started.",
        source="CELERY",
        request_id=task_id,
        metadata=task_metadata,
    )
    try:
        sent = send_mail(
            subject=subject,
            message=body,
            from_email=None,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        record_event(
            event_type="EMAIL_SENT",
            category="NOTIFICATION",
            severity="INFO",
            status="SUCCESS",
            actor="SYSTEM",
            message="Notification email sent.",
            source="CELERY",
            request_id=task_id,
            metadata={"recipient_count": len(recipient_list), "sent_count": sent},
        )
        record_event(
            event_type="TASK_SUCCESS",
            category="CELERY",
            severity="INFO",
            status="SUCCESS",
            actor="SYSTEM",
            message="Notification email task succeeded.",
            source="CELERY",
            request_id=task_id,
            metadata={**task_metadata, "sent_count": sent},
        )
        logger.info("Notification email sent to %s: %s", recipient_list, subject)
        return {"sent": sent, "recipients": recipient_list}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            record_event(
                event_type="EMAIL_FAILED",
                category="NOTIFICATION",
                severity="ERROR",
                status="FAILED",
                actor="SYSTEM",
                message="Notification email failed permanently.",
                source="CELERY",
                request_id=task_id,
                metadata={
                    "recipient_count": len(recipient_list),
                    "retry_count": self.request.retries,
                },
            )
            record_event(
                event_type="TASK_FAILED",
                category="CELERY",
                severity="ERROR",
                status="FAILED",
                actor="SYSTEM",
                message="Notification email task failed permanently.",
                source="CELERY",
                request_id=task_id,
                metadata={**task_metadata, "retry_count": self.request.retries},
            )
            logger.exception("Notification email failed permanently: %s", subject)
            raise

        countdown = min(60 * (2 ** self.request.retries), 15 * 60)
        record_event(
            event_type="EMAIL_RETRY",
            category="NOTIFICATION",
            severity="WARNING",
            status="RETRY",
            actor="SYSTEM",
            message="Notification email scheduled for retry.",
            source="CELERY",
            request_id=task_id,
            metadata={
                "recipient_count": len(recipient_list),
                "retry_count": self.request.retries + 1,
                "max_retries": self.max_retries,
            },
        )
        record_event(
            event_type="TASK_RETRY",
            category="CELERY",
            severity="WARNING",
            status="RETRY",
            actor="SYSTEM",
            message="Notification email task scheduled for retry.",
            source="CELERY",
            request_id=task_id,
            metadata={**task_metadata, "retry_count": self.request.retries + 1},
        )
        logger.warning(
            "Notification email failed; retrying in %s seconds (attempt %s/%s): %s",
            countdown,
            self.request.retries + 1,
            self.max_retries,
            exc,
        )
        raise self.retry(exc=exc, countdown=countdown)
