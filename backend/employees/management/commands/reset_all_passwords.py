from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from employees.models import Employee


class Command(BaseCommand):
    help = "Disable all user passwords and require administrators to assign new ones."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm the irreversible bulk password reset.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError(
                "This changes every account password. Re-run with --confirm to proceed."
            )

        users = list(User.objects.select_for_update().order_by("pk"))
        employees = {
            employee.user_id: employee
            for employee in Employee.objects.select_for_update().filter(
                user_id__in=[user.pk for user in users]
            )
        }

        updated = 0
        for user in users:
            user.set_unusable_password()
            user.save(update_fields=["password"])

            employee = employees.get(user.pk)
            if employee:
                employee.must_change_password = True
                employee.save(update_fields=["must_change_password"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Passwords updated: {updated}"))
        if updated:
            self.stdout.write(
                "All affected accounts now have unusable passwords. An "
                "administrator must assign new passwords before sign-in."
            )
