"""Shared date classification primitives for holiday-aware features.

These helpers intentionally do not replace existing attendance or leave rules
until those domains are migrated in the next phase.
"""

from datetime import date

from .models import Holiday


def is_weekend(target_date: date) -> bool:
    return target_date.weekday() in (5, 6)


def is_company_holiday(target_date: date) -> bool:
    return Holiday.objects.filter(date=target_date, is_active=True).exists()


def get_day_classifications(target_dates) -> dict:
    """Resolve multiple dates with one active-holiday query."""
    dates = set(target_dates)
    holidays_by_date = {
        holiday.date: holiday
        for holiday in Holiday.objects.filter(date__in=dates, is_active=True).only("date", "name")
    }
    classifications = {}
    for target_date in dates:
        holiday = holidays_by_date.get(target_date)
        weekend = is_weekend(target_date)
        classifications[target_date] = {
            "day_type": "WEEKEND" if weekend else "HOLIDAY" if holiday else "WORKING_DAY",
            "is_weekend": weekend,
            "is_company_holiday": holiday is not None,
            "is_working_day": not weekend and holiday is None,
            "attendance_required": not weekend and holiday is None,
            "holiday_name": holiday.name if holiday else None,
        }
    return classifications


def get_day_classification(target_date: date) -> dict:
    """Resolve one business date, keeping weekly and company holidays distinct."""
    return get_day_classifications([target_date])[target_date]


def get_non_working_dates(start_date: date, end_date: date) -> list[date]:
    """Return weekend and active company holiday dates in an inclusive range."""
    dates = []
    current = start_date
    from datetime import timedelta
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    classifications = get_day_classifications(dates)
    return [target for target in dates if not classifications[target]["attendance_required"]]


def is_working_day(target_date: date) -> bool:
    return get_day_classification(target_date)["is_working_day"]


def attendance_required(target_date: date) -> bool:
    return get_day_classification(target_date)["attendance_required"]
