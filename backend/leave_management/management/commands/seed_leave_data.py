from datetime import date
from django.core.management.base import BaseCommand
from leave_management.models import LeaveType, LeavePolicy


class Command(BaseCommand):
    help = "Seed initial Leave Types and Leave Policies"

    def handle(self, *args, **options):
        self.stdout.write("Seeding leave types...")

        types_data = [
            {
                "name": "Casual Leave",
                "code": "CASUAL",
                "description": "Standard casual leave for personal reasons",
                "is_paid": True,
                "allow_half_day": True,
                "min_notice_days": 0,
            },
            {
                "name": "Sick Leave",
                "code": "SICK",
                "description": "Leave for medical reasons and health recovery",
                "is_paid": True,
                "allow_half_day": True,
                "requires_document": True,
                "min_notice_days": 0,
            },
            {
                "name": "Earned Leave",
                "code": "EARNED",
                "description": "Privilege/Earned leave accrued through continuous service",
                "is_paid": True,
                "allow_half_day": False,
                "min_notice_days": 2,
            },
            {
                "name": "Privileged Leave",
                "code": "PRIVILEGED",
                "description": "Special privileged leave for extended vacations or events",
                "is_paid": True,
                "allow_half_day": False,
                "min_notice_days": 3,
            },
            {
                "name": "Unpaid Leave",
                "code": "UNPAID",
                "description": "Leave without pay when paid balances are exhausted",
                "is_paid": False,
                "allow_half_day": True,
                "min_notice_days": 0,
            },
            {
                "name": "Optional Holiday",
                "code": "OPTIONAL_HOLIDAY",
                "description": "Restricted/Optional holiday from company holiday list",
                "is_paid": True,
                "allow_half_day": False,
                "min_notice_days": 1,
            },
        ]

        created_types = {}
        for item in types_data:
            lt, created = LeaveType.objects.get_or_create(
                code=item["code"],
                defaults=item,
            )
            created_types[item["code"]] = lt
            if created:
                self.stdout.write(self.style.SUCCESS(f"  + Created LeaveType: {lt.name}"))
            else:
                self.stdout.write(f"  - LeaveType already exists: {lt.name}")

        self.stdout.write("Seeding leave policies...")
        effective_date = date(2026, 1, 1)

        policies_data = [
            # PERMANENT
            {"employee_type": "PERMANENT", "code": "CASUAL", "annual_entitlement": 12.0, "allow_carry_forward": True, "max_carry_forward": 5.0},
            {"employee_type": "PERMANENT", "code": "SICK", "annual_entitlement": 10.0, "requires_document": True},
            {"employee_type": "PERMANENT", "code": "EARNED", "annual_entitlement": 15.0, "allow_carry_forward": True, "max_carry_forward": 10.0, "min_notice_days": 2},
            {"employee_type": "PERMANENT", "code": "PRIVILEGED", "annual_entitlement": 10.0, "min_notice_days": 3},
            {"employee_type": "PERMANENT", "code": "UNPAID", "annual_entitlement": 30.0},
            {"employee_type": "PERMANENT", "code": "OPTIONAL_HOLIDAY", "annual_entitlement": 2.0, "min_notice_days": 1},

            # CONTRACT
            {"employee_type": "CONTRACT", "code": "CASUAL", "annual_entitlement": 6.0},
            {"employee_type": "CONTRACT", "code": "SICK", "annual_entitlement": 5.0},
            {"employee_type": "CONTRACT", "code": "UNPAID", "annual_entitlement": 15.0},

            # INTERN
            {"employee_type": "INTERN", "code": "CASUAL", "annual_entitlement": 2.0},
            {"employee_type": "INTERN", "code": "SICK", "annual_entitlement": 2.0},
            {"employee_type": "INTERN", "code": "UNPAID", "annual_entitlement": 10.0},
        ]

        for item in policies_data:
            lt = created_types.get(item["code"])
            if not lt:
                continue

            policy, created = LeavePolicy.objects.get_or_create(
                employee_type=item["employee_type"],
                leave_type=lt,
                effective_from=effective_date,
                defaults={
                    "annual_entitlement": item.get("annual_entitlement", 0.0),
                    "allow_carry_forward": item.get("allow_carry_forward", False),
                    "max_carry_forward": item.get("max_carry_forward", 0.0),
                    "min_notice_days": item.get("min_notice_days", 0),
                    "requires_document": item.get("requires_document", False),
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  + Created Policy: {item['employee_type']} - {lt.name} ({item.get('annual_entitlement')} days)"))

        self.stdout.write(self.style.SUCCESS("Leave management seeding completed successfully."))
