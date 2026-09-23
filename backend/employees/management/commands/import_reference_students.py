import re
import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from employees.models import Employee


STUDENTS = [
    ("Tanvi Kad", "C", "C1"),
    ("Jasleen Kaur", "C", "C1"),
    ("Ashish Rai", "C", "C1"),
    ("Manisha Parihar", "C", "C2"),
    ("Aryan Sharma", "C", "C2"),
    ("Prince Kumar", "B", "B1"),
    ("Maddirala Namitha Reddy", "A", "A2"),
    ("Sourabh Pal", "A", "A2"),
    ("Pandraju Ganya Srihitha", "A", "A1"),
    ("Akansha Attri", "C", "C2"),
    ("Akshat Bansal", "C", "C2"),
    ("Vakkalagadda Naga Venkata Sai Lakshmi Kanishka", "A", "A2"),
    ("Aditya", "C", "C1"),
    ("Jatin", "C", "C2"),
    ("Bhavya Bhutani", "C", "C2"),
    ("Krish Jain", "C", "C1"),
    ("Sanka Maruthi Srujan", "A", "A1"),
    ("Anushka Khare", "C", "C2"),
    ("Pramod", "A", "A1"),
    ("Somepalli Ravi Teja", "A", "A1"),
    ("Siddhesh Nitin Chawande", "A", "A2"),
    ("Aditya Yadav", "A", "A2"),
    ("Saksham Gupta", "A", "A2"),
    ("Jangeti Chaithanya Sai", "A", "A1"),
    ("K. Sriram Naveen", "A", "A1"),
    ("Khushal Nivas Gourishetty", "A", "A2"),
    ("Talapanti Rajesh", "A", "A2"),
    ("Somanadh Mendu", "A", "A1"),
    ("Keshav Agarwal", "A", "A1"),
    ("Mayank Jain Malu", "B", "B2"),
    ("Akshat Awasthi", "C", "C1"),
    ("Divyom Agarwal", "B", "B2"),
    ("Ayush V Panicker", "A", "A2"),
    ("Anshuman Mathur", "B", "B2"),
    ("Ayush Rai", "B", "B2"),
    ("Sarthak Shah", "B", "B1"),
    ("Aakash Yadav", "D", "D2"),
    ("Anushka Sharma", "D", "D2"),
    ("Tanmay Garg", "D", "D1"),
    ("Himanshu Gupta", "D", "D1"),
    ("Sameer Shukla", "D", "D1"),
    ("Darsheel Jaiswal", "B", "B2"),
    ("Anant Sharma", "D", "D2"),
    ("Titirsha Singh", "D", "D2"),
    ("Anshuman Mishra", "D", "D1"),
    ("Anant Vaibhav", "D", "D2"),
    ("Rudraraju Sriram Sathvik Varma", "B", "B1"),
    ("Ananya Jain", "C", "C1"),
    ("Nikhil Bisla", "D", "D2"),
    ("Pradeep Varma", "B", "B2"),
    ("Mann Upadhyay", "B", "B2"),
    ("Aditi Gupta", "C", "C1"),
    ("Garvita Singh", "B", "B1"),
    ("Nitin Singh", "B", "B1"),
    ("Pranav Suresh", "B", "B1"),
    ("Rohit Raghav", "B", "B2"),
    ("Kanak Varshney", "B", "B1"),
    ("Bharat Yadav", "B", "B1"),
    ("Sridhar Reddy", "B", "B2"),
    ("Mahendra Reddy", "B", "B1"),
    ("Sivaram Saran", "B", "B1"),
    ("Ansh Kukreti", "C", "C1"),
    ("Jatin Malik", "C", "C2"),
    ("Keshav Gupta", "C", "C1"),
    ("Deepanshu", "B", "B2"),
    ("Harsh Kumar", "B", "B2"),
    ("Divyansh Agarwal", "D", "D1"),
    ("Yash", "D", "D1"),
    ("Arth Saxena", "D", "D2"),
    ("Khushi Bainsla", "D", "D1"),
    ("Piyush Yadav", "D", "D2"),
    ("Nitin Aman", "D", "D1"),
    ("Vaivashvat Upadhyay", "D", "D2"),
    ("Athira Ravi Pillai", "D", "D2"),
    ("D Anil Kumar", "A", "A1"),
    ("Yayivi Vinay", "A", "A1"),
    ("Nikhil Sai Vamshi Krishna Manam", "A", "A2"),
    ("Saloni Rana", "D", "D1"),
    ("Nishant Sindhu", "D", "D1"),
    ("Jayesh Kansal", "C", "C2"),
]


def normalize_name(name):
    return " ".join(name.casefold().split())


def email_slug(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", ".", ascii_name.casefold()).strip(".")


class Command(BaseCommand):
    help = "Add missing reference students without changing existing employee records."

    def handle(self, *args, **options):
        supplied = len(STUDENTS)
        existing_users = list(User.objects.select_related("employee"))
        existing_emails = {user.email.casefold() for user in existing_users}
        existing_names = {
            normalize_name(f"{user.first_name} {user.last_name}")
            for user in existing_users
            if hasattr(user, "employee")
        }
        skipped = []
        added = []
        failed = []
        generated_emails = set(existing_emails)
        today = timezone.localdate()

        for full_name, section, subsection in STUDENTS:
            normalized_name = normalize_name(full_name)
            base_email = f"{email_slug(full_name)}@dailoqa.com"
            email = base_email
            if normalized_name in existing_names or email.casefold() in generated_emails:
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
                generated_emails.add(email.casefold())
                existing_names.add(normalized_name)
                added.append((full_name, section, subsection))
            except Exception as error:
                failed.append((full_name, str(error)))

        self.stdout.write(f"Total supplied students: {supplied}")
        self.stdout.write(f"Already existed / skipped: {len(skipped)}")
        self.stdout.write(f"Newly added: {len(added)}")
        self.stdout.write(f"Failed: {len(failed)}")
        self.stdout.write("\nAlready existed:")
        for index, name in enumerate(skipped, 1):
            self.stdout.write(f"{index}. {name}")
        self.stdout.write("\nNewly added:")
        for index, (name, section, subsection) in enumerate(added, 1):
            self.stdout.write(f"{index}. {name} — Section {section} — {subsection}")
        if failed:
            self.stdout.write("\nFailed details:")
            for name, error in failed:
                self.stdout.write(f"- {name}: {error}")
