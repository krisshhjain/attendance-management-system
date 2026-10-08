"""Backward-compatible imports for the centralized holiday date resolver."""

import datetime

from holidays.services import is_company_holiday

def is_working_day(date_obj: datetime.date) -> bool:
    """Return whether attendance is required on the date."""
    from holidays.services import is_working_day as resolve_working_day
    return resolve_working_day(date_obj)

def is_holiday(date_obj: datetime.date) -> bool:
    """Return whether this date is an active named company holiday.

    Weekends are weekly non-working days and are intentionally not company holidays.
    """
    return is_company_holiday(date_obj)
