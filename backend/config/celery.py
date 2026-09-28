import os

from celery import Celery
from celery.apps.worker import Worker as CeleryWorker

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY_")
app.autodiscover_tasks()


class RabbitMQWorker(CeleryWorker):
	def __init__(self, *args, **kwargs):
		kwargs["without_mingle"] = True
		kwargs["without_gossip"] = True
		super().__init__(*args, **kwargs)


app.Worker = app.subclass_with_self(RabbitMQWorker)
