import datetime

def is_working_day(date_obj: datetime.date) -> bool:
    """
    CENTRAL BUSINESS RULE:
    Saturday (5) and Sunday (6) are official weekly holidays.
    Returns True if the given date is a working day, False if it is a weekend/holiday.
    """
    return date_obj.weekday() not in (5, 6)

def is_holiday(date_obj: datetime.date) -> bool:
    """
    Returns True if the date is an official holiday (weekend).
    """
    return not is_working_day(date_obj)
