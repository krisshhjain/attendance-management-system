from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hr_copilot", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="CopilotConversationContext",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("conversation_id", models.CharField(max_length=128)),
                ("context", models.JSONField(default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("user", "conversation_id"), name="hr_copilot_user_conversation")]},
        ),
    ]
