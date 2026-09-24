from django.conf import settings
from django.db import models


class CopilotQueryAudit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    question = models.TextField()
    intent = models.JSONField(default=dict)
    query_plan = models.JSONField(default=dict)
    sql = models.TextField(blank=True, default="")
    validation_result = models.CharField(max_length=32, default="not_run")
    scope_result = models.CharField(max_length=32, default="not_run")
    execution_result = models.CharField(max_length=32, default="not_run")
    error_code = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
