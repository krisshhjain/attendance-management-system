from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0014_alter_attendance_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendanceevent",
            name="correction",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="attendance_events",
                to="attendance.attendancecorrection",
            ),
        ),
    ]
