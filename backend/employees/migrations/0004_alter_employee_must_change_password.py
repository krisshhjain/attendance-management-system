from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0003_employee_app_access"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employee",
            name="must_change_password",
            field=models.BooleanField(default=True),
        ),
    ]
