from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AttendanceEvent
from .tasks import create_attendance_notification


@receiver(post_save, sender=AttendanceEvent)
def queue_attendance_notification(sender, instance, created, **kwargs):
    if not created:
        return

    attendance_event_id = instance.pk
    transaction.on_commit(
        lambda event_id=attendance_event_id: create_attendance_notification.delay(
            event_id
        )
    )
