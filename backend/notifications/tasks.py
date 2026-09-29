import logging

from celery import shared_task
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, name="notifications.send_notification_email")
def send_notification_email(self, recipient_list, subject, body):
    """Send notification email asynchronously with bounded transient retries."""
    try:
        sent = send_mail(
            subject=subject,
            message=body,
            from_email=None,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info("Notification email sent to %s: %s", recipient_list, subject)
        return {"sent": sent, "recipients": recipient_list}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.exception("Notification email failed permanently: %s", subject)
            raise

        countdown = min(60 * (2 ** self.request.retries), 15 * 60)
        logger.warning(
            "Notification email failed; retrying in %s seconds (attempt %s/%s): %s",
            countdown,
            self.request.retries + 1,
            self.max_retries,
            exc,
        )
        raise self.retry(exc=exc, countdown=countdown)
