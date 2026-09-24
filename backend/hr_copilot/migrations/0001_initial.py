import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="CopilotQueryAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.TextField()),
                ("intent", models.JSONField(default=dict)),
                ("query_plan", models.JSONField(default=dict)),
                ("sql", models.TextField(blank=True, default="")),
                ("validation_result", models.CharField(default="not_run", max_length=32)),
                ("scope_result", models.CharField(default="not_run", max_length=32)),
                ("execution_result", models.CharField(default="not_run", max_length=32)),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
