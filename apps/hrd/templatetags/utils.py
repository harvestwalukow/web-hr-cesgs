from django import template
import calendar

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(int(key))

@register.filter
def to_list(start, end):
    return range(start, end + 1)

@register.filter
def get_month_name(month_number):
    """Convert month number to month name"""
    try:
        return calendar.month_name[int(month_number)]
    except (ValueError, IndexError):
        return month_number
