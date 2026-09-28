from celery import shared_task


@shared_task
def test_celery_task(message):
    print(f"[Celery Test Task] {message}")
    return message