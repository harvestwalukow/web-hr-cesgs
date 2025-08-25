from django import template
from datetime import datetime, date

register = template.Library()

@register.filter
def duration_days(start_date, end_date):
    """Calculate the number of days between two dates (inclusive)."""
    if not start_date or not end_date:
        return 0
    
    # Convert to date objects if they are datetime objects
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    # Calculate the difference and add 1 to make it inclusive
    delta = end_date - start_date
    return delta.days + 1

@register.filter
def month_name_id(month_number):
    """Convert month number to Indonesian month name."""
    months = {
        1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
        5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
        9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
    }
    return months.get(month_number, '')