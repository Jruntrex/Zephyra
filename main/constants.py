"""
Constants для Zephyra

Цей модуль містить всі константи проекту:
- Ролі користувачів
- Дні тижня
- Часові слоти (дзвінки)
- Коди пропусків
"""

from datetime import time
from enum import Enum


class UserRole(str, Enum):
    """Ролі користувачів у системі."""

    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"

    @classmethod
    def choices(cls):
        """Для використання в Django моделях."""
        return [(role.value, role.name.title()) for role in cls]


class DayOfWeek(int, Enum):
    """Дні тижня (ISO стандарт: 1=Понеділок, 7=Неділя)."""

    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7

    @classmethod
    def get_name_uk(cls, day: int) -> str:
        """Отримати українську назву дня."""
        names = {
            1: "Понеділок",
            2: "Вівторок",
            3: "Середа",
            4: "Четвер",
            5: "П'ятниця",
            6: "Субота",
            7: "Неділя",
        }
        return names.get(day, "")

    @classmethod
    def get_short_name_uk(cls, day: int) -> str:
        """Отримати скорочену українську назву дня."""
        names = {
            1: "Пн",
            2: "Вт",
            3: "Ср",
            4: "Чт",
            5: "Пт",
            6: "Сб",
            7: "Нд",
        }
        return names.get(day, "")


# Стандартний розклад дзвінків
# Формат: номер_пари -> (час_початку, час_кінця)
# 3 пари зранку (8:00-10:50), велика перерва, 3 пари після (12:00-14:50), +7-а за потреби
DEFAULT_TIME_SLOTS = {
    1: (time(8, 0), time(8, 50)),
    2: (time(9, 0), time(9, 50)),
    3: (time(10, 0), time(10, 50)),
    4: (time(12, 0), time(12, 50)),
    5: (time(13, 0), time(13, 50)),
    6: (time(14, 0), time(14, 50)),
    7: (time(15, 0), time(15, 50)),
}

# Альтернативний формат (для зворотної сумісності)
# ПОПЕРЕДЖЕННЯ: Використовуйте DEFAULT_TIME_SLOTS для нових розробок
DEFAULT_LESSON_TIMES = {
    1: "08:00",
    2: "09:00",
    3: "10:00",
    4: "12:00",
    5: "13:00",
    6: "14:00",
    7: "15:00",
}

# Тривалість стандартної пари (хвилини)
DEFAULT_LESSON_DURATION = 50


class AbsenceCode(str, Enum):
    """Коди пропусків."""

    ABSENT = "Н"  # Неповажна причина
    DISTANCE = "ДЛ"  # Дистанційне навчання
    VALID_REASON = "ПП"  # Поважна причина
    SICK = "Б"  # Хвороба
    VACATION = "В"  # Відпустка

    @classmethod
    def get_code_value(cls, code: str) -> int:
        """Конвертація коду у числове значення (для старої системи)."""
        mapping = {
            "Н": -1,
            "ДЛ": -2,
            "ПП": -3,
            "Б": -4,
            "В": -5,
        }
        return mapping.get(code, -1)

    @classmethod
    def get_value_code(cls, value: int) -> str:
        """Конвертація числового значення у код (для старої системи)."""
        mapping = {
            -1: "Н",
            -2: "ДЛ",
            -3: "ПП",
            -4: "Б",
            -5: "В",
        }
        return mapping.get(value, "Н")


# Мінімальний та максимальний бал (12-бальна шкала)
MIN_GRADE = 1
MAX_GRADE = 12

# Порогові значення 12-бальної шкали
GRADE_SCALE_THRESHOLDS = {
    "Відмінно": 12,
    "Дуже добре": 10,
    "Добре": 7,
    "Задовільно": 4,
    "Незадовільно": 1,
}

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Формати дат
DATE_FORMAT_SHORT = "%d.%m"
DATE_FORMAT_FULL = "%d.%m.%Y"
DATE_FORMAT_ISO = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"
