from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from attendance.models import Attendance
from config.business_rules import is_working_day
from .models import LeavePolicy, LeaveRequest, LeaveType


def calculate_working_days(start_date, end_date, day_type="FULL_DAY"):
    if start_date > end_date:
        return Decimal("0.0")

    if start_date == end_date and day_type in ("FIRST_HALF", "SECOND_HALF"):
        # Check if single day is weekend
        if not is_working_day(start_date):
            return Decimal("0.0")
        return Decimal("0.5")

    total_days = Decimal("0.0")
    curr = start_date
    while curr <= end_date:
        if is_working_day(curr):
            total_days += Decimal("1.0")
        curr += timedelta(days=1)

    return total_days


def get_active_policy(employee, leave_type, target_date=None):
    if target_date is None:
        target_date = timezone.localdate()

    policies = LeavePolicy.objects.filter(
        employee_type=employee.employment_type,
        leave_type=leave_type,
        is_active=True,
        effective_from__lte=target_date,
    ).order_by("-effective_from")

    for pol in policies:
        if pol.effective_to is None or pol.effective_to >= target_date:
            return pol

    return None


def calculate_employee_leave_balances(employee, year=None):
    if year is None:
        year = timezone.localdate().year

    leave_types = LeaveType.objects.filter(is_active=True).order_by("name")
    balances = []

    for lt in leave_types:
        policy = get_active_policy(employee, lt, target_date=date(year, 1, 1))
        if not policy:
            # Fallback to any active policy for today
            policy = get_active_policy(employee, lt)

        entitlement = Decimal(str(policy.annual_entitlement)) if policy else Decimal("0.0")
        allow_carry_forward = policy.allow_carry_forward if policy else False
        max_carry_forward = Decimal(str(policy.max_carry_forward)) if policy else Decimal("0.0")

        # Calculate carried forward from previous year if policy allows
        carried_forward = Decimal("0.0")
        if allow_carry_forward:
            prev_year_policy = get_active_policy(employee, lt, target_date=date(year - 1, 1, 1))
            if prev_year_policy:
                prev_entitlement = Decimal(str(prev_year_policy.annual_entitlement))
                prev_approved = LeaveRequest.objects.filter(
                    employee=employee,
                    leave_type=lt,
                    status="APPROVED",
                    start_date__year=year - 1,
                )
                prev_used = sum([req.duration_days for req in prev_approved], Decimal("0.0"))
                unused_prev = max(Decimal("0.0"), prev_entitlement - prev_used)
                carried_forward = min(unused_prev, max_carry_forward)

        # Approved used for current year
        approved_requests = LeaveRequest.objects.filter(
            employee=employee,
            leave_type=lt,
            status="APPROVED",
            start_date__year=year,
        )
        used = sum([req.duration_days for req in approved_requests], Decimal("0.0"))

        # Pending for current year
        pending_requests = LeaveRequest.objects.filter(
            employee=employee,
            leave_type=lt,
            status="PENDING",
            start_date__year=year,
        )
        pending = sum([req.duration_days for req in pending_requests], Decimal("0.0"))

        available = max(Decimal("0.0"), entitlement + carried_forward - used)

        balances.append({
            "leave_type_id": lt.id,
            "leave_type_name": lt.name,
            "leave_type_code": lt.code,
            "is_paid": lt.is_paid,
            "annual_entitlement": float(entitlement),
            "carried_forward": float(carried_forward),
            "used": float(used),
            "pending": float(pending),
            "available": float(available),
            "requires_document": policy.requires_document if policy else lt.requires_document,
            "allow_half_day": policy.allow_half_day if policy else lt.allow_half_day,
            "max_consecutive_days": policy.max_consecutive_days if policy else 10,
            "min_notice_days": policy.min_notice_days if policy else lt.min_notice_days,
        })

    return balances


def validate_leave_request(employee, leave_type, start_date, end_date, day_type="FULL_DAY", reason="", attachment=""):
    if not employee.is_active:
        raise ValidationError("Inactive employee cannot submit leave requests.")

    if not leave_type.is_active:
        raise ValidationError(f"Leave type '{leave_type.name}' is currently inactive.")

    if start_date > end_date:
        raise ValidationError("Start date cannot be after end date.")

    today = timezone.localdate()

    if not leave_type.allow_past_dates and start_date < today:
        raise ValidationError("Leave request for past dates is not allowed for this leave type.")

    if not leave_type.allow_future_dates and start_date > today:
        raise ValidationError("Leave request for future dates is not allowed for this leave type.")

    if day_type in ("FIRST_HALF", "SECOND_HALF"):
        if not leave_type.allow_half_day:
            raise ValidationError(f"Half-day leave is not allowed for {leave_type.name}.")
        if start_date != end_date:
            raise ValidationError("Half-day leave can only be requested for a single day.")

    duration = calculate_working_days(start_date, end_date, day_type)
    if duration <= Decimal("0.0"):
        raise ValidationError("Selected date range contains no working days (e.g. weekend only).")

    policy = get_active_policy(employee, leave_type, target_date=start_date)

    # Minimum notice period check
    min_notice = policy.min_notice_days if policy else leave_type.min_notice_days
    if min_notice > 0 and start_date > today:
        days_notice = (start_date - today).days
        if days_notice < min_notice:
            raise ValidationError(f"Minimum notice period for {leave_type.name} is {min_notice} days.")

    # Max consecutive days check
    max_consecutive = policy.max_consecutive_days if policy else 10
    if duration > max_consecutive:
        raise ValidationError(f"Maximum consecutive days allowed for {leave_type.name} is {max_consecutive} days.")

    # Documentation requirement check
    req_doc = policy.requires_document if policy else leave_type.requires_document
    if req_doc and not attachment:
        raise ValidationError(f"Supporting documentation is required for {leave_type.name}.")

    # Overlapping leave check (PENDING or APPROVED)
    overlapping = LeaveRequest.objects.filter(
        employee=employee,
        status__in=["PENDING", "APPROVED"],
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    if overlapping.exists():
        raise ValidationError("You already have a pending or approved leave request for this date range.")

    # Available balance check for paid leave types
    if leave_type.is_paid:
        year_balances = calculate_employee_leave_balances(employee, year=start_date.year)
        lt_balance = next((b for b in year_balances if b["leave_type_id"] == leave_type.id), None)
        if lt_balance:
            available = Decimal(str(lt_balance["available"]))
            if duration > available:
                raise ValidationError(f"Insufficient leave balance for {leave_type.name}. Requested: {duration} days, Available: {available} days.")

    return duration


@transaction.atomic
def approve_leave_request(leave_request, reviewer_user, remarks=""):
    req = LeaveRequest.objects.select_for_update().get(id=leave_request.id)

    if req.status != "PENDING":
        raise ValidationError(f"Cannot approve leave request with status '{req.status}'. Only PENDING requests can be approved.")

    req.status = "APPROVED"
    req.reviewed_at = timezone.now()
    req.reviewed_by = reviewer_user
    req.reviewer_remarks = remarks
    req.save()

    # Integrate with Attendance records
    curr = req.start_date
    while curr <= req.end_date:
        if is_working_day(curr):
            att, created = Attendance.objects.get_or_create(
                employee=req.employee,
                date=curr,
            )
            att.status = "LEAVE"
            att.leave_request = req
            att.save()
        curr += timedelta(days=1)

    return req


@transaction.atomic
def deny_leave_request(leave_request, reviewer_user, remarks):
    req = LeaveRequest.objects.select_for_update().get(id=leave_request.id)

    if req.status != "PENDING":
        raise ValidationError(f"Cannot deny leave request with status '{req.status}'. Only PENDING requests can be denied.")

    if not remarks or not remarks.strip():
        raise ValidationError("Reviewer remarks are required when denying a leave request.")

    req.status = "DENIED"
    req.reviewed_at = timezone.now()
    req.reviewed_by = reviewer_user
    req.reviewer_remarks = remarks
    req.save()

    return req


@transaction.atomic
def cancel_leave_request(leave_request, user):
    req = LeaveRequest.objects.select_for_update().get(id=leave_request.id)

    if req.status == "CANCELLED":
        raise ValidationError("Leave request is already cancelled.")

    is_admin = bool(user and (user.is_staff or user.is_superuser))
    if not is_admin:
        if req.status not in ["PENDING", "APPROVED"]:
            raise ValidationError("Employees can only cancel PENDING or APPROVED leave requests.")

    was_approved = (req.status == "APPROVED")

    req.status = "CANCELLED"
    req.cancelled_at = timezone.now()
    req.cancelled_by = user
    req.save()

    if was_approved:
        # Revert associated attendance records that have status='LEAVE' and no check_in
        Attendance.objects.filter(
            leave_request=req,
            check_in__isnull=True,
        ).delete()

        # For attendance records that might have check_in, detach leave_request
        Attendance.objects.filter(
            leave_request=req,
        ).update(leave_request=None)

    return req
