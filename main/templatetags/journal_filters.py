# main/templatetags/journal_filters.py
import json
from datetime import date as dt_date
from datetime import timedelta

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return None
    try:
        return dictionary.get(key)
    except AttributeError:
        return getattr(dictionary, key, None)


@register.simple_tag
def get_lesson_at(lessons, date_obj, lesson_num):
    """Шукає урок для конкретної дати та номеру пари."""
    times = {
        1: "08:00",
        2: "09:00",
        3: "10:00",
        4: "12:00",
        5: "13:00",
        6: "14:00",
        7: "15:00",
    }
    target_time = times.get(int(lesson_num))
    if not target_time or not lessons:
        return None

    for l in lessons:
        try:
            if l.date == date_obj and l.start_time.strftime("%H:%M") == target_time:
                return l
        except:
            continue
    return None


@register.simple_tag
def get_schedule_template_at(templates, day_of_week, lesson_num):
    """Шукає шаблон розкладу для конкретного дня тижня та номеру пари."""
    if not templates:
        return None

    lesson_num_int = int(lesson_num)
    day_int = int(day_of_week)

    for t in templates:
        if t.day_of_week == day_int and t.lesson_number == lesson_num_int:
            return t
    return None


@register.simple_tag
def lesson_hours(num):
    """Повертає часовий інтервал для номеру пари."""
    times = {
        1: "08:00 - 08:50",
        2: "09:00 - 09:50",
        3: "10:00 - 10:50",
        4: "12:00 - 12:50",
        5: "13:00 - 13:50",
        6: "14:00 - 14:50",
        7: "15:00 - 15:50",
    }
    return times.get(int(num), "")


@register.filter
def format_teacher_short(full_name):
    """Форматує ПІБ: Прізвище І. О."""
    if not full_name:
        return ""
    parts = full_name.split()
    if len(parts) >= 2:
        res = f"{parts[0]} {parts[1][0]}."
        if len(parts) >= 3:
            res += f" {parts[2][0]}."
        return res
    return full_name


@register.filter
def to_json(value):
    if value is None:
        return "null"
    return json.dumps(value)


@register.filter
def is_equal(value, arg):
    return str(value) == str(arg)


@register.filter
def split(value, arg):
    return str(value).split(arg)


@register.filter
def modulo(value, arg):
    try:
        return int(value) % int(arg)
    except:
        return 0


@register.filter
def date_bucket(value):
    """Returns 'today', 'tomorrow', or '' for a date object."""
    try:
        today = dt_date.today()
        if value == today:
            return "today"
        if value == today + timedelta(days=1):
            return "tomorrow"
        return ""
    except Exception:
        return ""


@register.filter
def get_hw_weight(lesson, hw_weights):
    """Повертає відсоток ДЗ для уроку з dict {subj_id_grp_id: weight}."""
    if not hw_weights:
        return None
    key = f"{lesson.subject_id}_{lesson.group_id}"
    return hw_weights.get(key)


# Dummy filters for compatibility with old templates if any
@register.filter
def time_to_offset(val, arg=0):
    return 0


@register.filter
def duration_to_height(val):
    return 90
