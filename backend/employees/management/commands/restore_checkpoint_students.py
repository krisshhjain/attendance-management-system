"""Restore the reference student roster after a database checkpoint reset."""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from employees.models import Employee
from employees.management.commands.import_reference_students import (
    STUDENTS,
    email_slug,
    normalize_name,
)


class Command(BaseCommand):
    help = "Restore missing reference students without changing existing records."

    def handle(self, *args, **options):
        existing_users = list(User.objects.select_related("employee"))
        existing_emails = {user.email.casefold() for user in existing_users}
        existing_names = {
            normalize_name(f"{user.first_name} {user.last_name}")
            for user in existing_users
            if hasattr(user, "employee")
        }

        added = []
        skipped = []
        failed = []
        today = timezone.localdate()

        for full_name, section, subsection in STUDENTS:
            normalized_name = normalize_name(full_name)
            email = f"{email_slug(full_name)}@dailoqa.com"

            if normalized_name in existing_names or email.casefold() in existing_emails:
                skipped.append(full_name)
                continue

            first_name, *last_parts = full_name.split()
            last_name = " ".join(last_parts)
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email,
                        password=f"{first_name}@123",
                        first_name=first_name,
                        last_name=last_name,
                    )
                    Employee.objects.create(
                        user=user,
                        department="Student",
                        employment_type="PERMANENT",
                        date_joined=today,
                        is_active=True,
                        must_change_password=True,
                        section=section,
                        subsection=subsection,
                    )
                existing_emails.add(email.casefold())
                existing_names.add(normalized_name)
                added.append(full_name)
            except Exception as error:
                failed.append((full_name, str(error)))

        self.stdout.write(f"Total supplied students: {len(STUDENTS)}")
        self.stdout.write(f"Already existed / skipped: {len(skipped)}")
        self.stdout.write(f"Newly added: {len(added)}")
        self.stdout.write(f"Failed: {len(failed)}")

        if skipped:
            self.stdout.write("\nAlready existed:")
            for name in skipped:
                self.stdout.write(f"- {name}")

        if added:
            self.stdout.write("\nNewly added:")
            for name in added:
                self.stdout.write(f"- {name}")

        if failed:
            self.stdout.write("\nFailed details:")
            for name, error in failed:
                self.stdout.write(f"- {name}: {error}")
