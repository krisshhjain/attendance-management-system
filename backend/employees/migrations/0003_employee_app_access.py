from django.db import migrations, models

import employees.models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0002_employee_must_change_password_employee_section_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="app_access",
            field=models.JSONField(blank=True, default=employees.models.default_app_access),
        ),
    ]
