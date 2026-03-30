# main/templatetags/math_filters.py
from django import template

register = template.Library()


@register.filter
def mul(value, arg):
    """Множить аргументи."""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return ""


@register.filter
def sub(value, arg):
    """Віднімає аргумент від значення."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return ""
