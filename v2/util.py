'''
Utility functions for v2 task management system.
'''

from datetime import date, timedelta


def get_week_start(dt: date | None = None) -> date:
    '''Get the start of the week (Monday) for a given date.

    Args:
        dt: Date to get week start for. Defaults to today.

    Returns:
        Date representing the start of the week (Monday)
    '''
    if dt is None:
        dt = date.today()

    # Get days since Monday (0 = Monday, 6 = Sunday)
    days_since_monday = dt.weekday()

    # Subtract days to get to Monday
    return dt - timedelta(days=days_since_monday)
