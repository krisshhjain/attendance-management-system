from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_user_is_system_admin")]
    operations = [
        migrations.AddField(
            model_name="user",
            name="hr_copilot_sections",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="user",
            name="hr_copilot_subsections",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
