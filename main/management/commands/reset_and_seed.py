"""
Management command: reset_and_seed

Повністю очищає БД (крім суперадміна) і заповнює тестовими даними:
  - 4 навчальні групи (КН-41, КН-42, КН-21, КН-22)
  - 40 студентів (10 на групу)
  - 12 викладачів
  - 15 предметів
  - Уроки за попередній, поточний та наступний тиждень
  - Оцінки та пропуски за попередній тиждень і поточний (до сьогодні включно)

Email / Пароль:
  Викладачі: ivan.kovalenko@teacher.zephyra.edu.ua  →  пароль: ivan.kovalenko
  Студенти:  anna.koval@student.zephyra.edu.ua       →  пароль: anna.koval

Профілі студентів (за індексом у групі, 0-based):
  0, 1  — відмінник    (10–12 балів, 3% пропусків)
  2, 3, 4 — хорошист  (7–9 балів,  7% пропусків)
  5, 6, 7 — середняк  (4–7 балів, 10% пропусків)
  8     — двієчник     (1–4 балів, 15% пропусків, переважно неповажних)
  9     — прогульник   (довільні бали, 40% пропусків)
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import (
    AbsenceReason,
    BuildingAccessLog,
    Classroom,
    Comment,
    EvaluationType,
    Lesson,
    Notification,
    Post,
    ScheduleTemplate,
    StudentPerformance,
    StudyGroup,
    Subject,
    TeachingAssignment,
    User,
)

# ── Date windows (розраховуються відносно сьогодні) ──────────────────────────
TODAY = date.today()
THIS_WEEK_MON = TODAY - timedelta(days=TODAY.weekday())
PREV_WEEK_MON = THIS_WEEK_MON - timedelta(weeks=1)
NEXT_WEEK_MON = THIS_WEEK_MON + timedelta(weeks=1)

START_DATE = PREV_WEEK_MON  # попередній пн
END_DATE = NEXT_WEEK_MON + timedelta(days=4)  # наступна пт
GRADES_CUTOFF = TODAY  # оцінки тільки до сьогодні

# ── Time slots ────────────────────────────────────────────────────────────────
TIME_MAP = {
    1: (time(8, 0), time(8, 50)),
    2: (time(9, 0), time(9, 50)),
    3: (time(10, 0), time(10, 50)),
    4: (time(12, 0), time(12, 50)),
    5: (time(13, 0), time(13, 50)),
}
LESSON_TYPE_CYCLE = ["lecture", "practical", "lab", "lecture", "practical"]

# ── Absence reasons ───────────────────────────────────────────────────────────
ABSENCE_REASONS_DATA = [
    {
        "code": "Н",
        "description": "Без поважної причини",
        "is_respectful": False,
        "color": "#e74c3c",
        "order": 1,
    },
    {
        "code": "Б",
        "description": "Хвороба",
        "is_respectful": True,
        "color": "#3498db",
        "order": 2,
    },
    {
        "code": "ПП",
        "description": "Поважна причина",
        "is_respectful": True,
        "color": "#2ecc71",
        "order": 3,
    },
    {
        "code": "ДЛ",
        "description": "Дистанційне навчання",
        "is_respectful": True,
        "color": "#9b59b6",
        "order": 4,
    },
    {
        "code": "В",
        "description": "Відпустка",
        "is_respectful": False,
        "color": "#f39c12",
        "order": 5,
    },
]

# ── Classrooms ────────────────────────────────────────────────────────────────
CLASSROOMS_DATA = [
    {
        "name": "101",
        "building": "Корпус А",
        "floor": 1,
        "capacity": 30,
        "type": "lecture",
    },
    {
        "name": "202",
        "building": "Корпус А",
        "floor": 2,
        "capacity": 25,
        "type": "lecture",
    },
    {
        "name": "305",
        "building": "Корпус А",
        "floor": 3,
        "capacity": 20,
        "type": "computer",
    },
    {
        "name": "306",
        "building": "Корпус А",
        "floor": 3,
        "capacity": 20,
        "type": "computer",
    },
    {
        "name": "Лаб-1",
        "building": "Корпус Б",
        "floor": 1,
        "capacity": 15,
        "type": "lab",
    },
    {
        "name": "Лаб-2",
        "building": "Корпус Б",
        "floor": 1,
        "capacity": 15,
        "type": "lab",
    },
    {
        "name": "201",
        "building": "Корпус Б",
        "floor": 2,
        "capacity": 40,
        "type": "lecture",
    },
    {
        "name": "401",
        "building": "Корпус В",
        "floor": 4,
        "capacity": 30,
        "type": "lecture",
    },
    {
        "name": "Комп-1",
        "building": "Корпус В",
        "floor": 2,
        "capacity": 25,
        "type": "computer",
    },
    {
        "name": "Комп-2",
        "building": "Корпус В",
        "floor": 2,
        "capacity": 25,
        "type": "computer",
    },
]

# ── Subjects (15) ─────────────────────────────────────────────────────────────
SUBJECTS_DATA = [
    {
        "name": "Вища математика",
        "code": "MATH-101",
        "credits": 5,
        "hours_total": 150,
        "semester": 1,
    },
    {
        "name": "Об'єктно-орієнтоване програмування",
        "code": "OOP-201",
        "credits": 4,
        "hours_total": 120,
        "semester": 3,
    },
    {
        "name": "Бази даних",
        "code": "DB-202",
        "credits": 4,
        "hours_total": 120,
        "semester": 3,
    },
    {
        "name": "Веб-технології",
        "code": "WEB-301",
        "credits": 4,
        "hours_total": 120,
        "semester": 5,
    },
    {
        "name": "Алгоритми та структури даних",
        "code": "ASD-203",
        "credits": 5,
        "hours_total": 150,
        "semester": 3,
    },
    {
        "name": "Комп'ютерні мережі",
        "code": "NET-302",
        "credits": 4,
        "hours_total": 120,
        "semester": 5,
    },
    {
        "name": "Комп'ютерна архітектура",
        "code": "ARCH-204",
        "credits": 3,
        "hours_total": 90,
        "semester": 4,
    },
    {
        "name": "Операційні системи",
        "code": "OS-303",
        "credits": 4,
        "hours_total": 120,
        "semester": 5,
    },
    {
        "name": "Дискретна математика",
        "code": "DM-102",
        "credits": 4,
        "hours_total": 120,
        "semester": 2,
    },
    {
        "name": "Програмування мовою Python",
        "code": "PY-205",
        "credits": 4,
        "hours_total": 120,
        "semester": 4,
    },
    {
        "name": "Штучний інтелект та МН",
        "code": "AI-401",
        "credits": 5,
        "hours_total": 150,
        "semester": 7,
    },
    {
        "name": "Мобільна розробка",
        "code": "MOB-402",
        "credits": 4,
        "hours_total": 120,
        "semester": 7,
    },
    {
        "name": "Безпека інформаційних систем",
        "code": "SEC-403",
        "credits": 4,
        "hours_total": 120,
        "semester": 7,
    },
    {
        "name": "Теорія ймовірностей та статистика",
        "code": "STAT-103",
        "credits": 4,
        "hours_total": 120,
        "semester": 2,
    },
    {
        "name": "Системне програмування",
        "code": "SYS-304",
        "credits": 4,
        "hours_total": 120,
        "semester": 6,
    },
]

# ── Groups (4) ────────────────────────────────────────────────────────────────
GROUPS_DATA = [
    {
        "name": "КН-41",
        "course": 4,
        "year_of_entry": 2022,
        "graduation_year": 2026,
        "specialty": "Комп'ютерні науки",
    },
    {
        "name": "КН-42",
        "course": 4,
        "year_of_entry": 2022,
        "graduation_year": 2026,
        "specialty": "Комп'ютерні науки",
    },
    {
        "name": "КН-21",
        "course": 2,
        "year_of_entry": 2024,
        "graduation_year": 2028,
        "specialty": "Комп'ютерні науки",
    },
    {
        "name": "КН-22",
        "course": 2,
        "year_of_entry": 2024,
        "graduation_year": 2028,
        "specialty": "Комп'ютерні науки",
    },
]

# ── Teachers (12) ─────────────────────────────────────────────────────────────
# email домен @teacher.zephyra.edu.ua — пароль = частина до @
TEACHERS_DATA = [
    {
        "full_name": "Іван Петрович Коваленко",
        "email": "ivan.kovalenko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Олена Василівна Петренко",
        "email": "olena.petrenko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Микола Іванович Сидоренко",
        "email": "mykola.sydorenko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Юлія Андріївна Бондаренко",
        "email": "yulia.bondarenko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Андрій Миколайович Мороз",
        "email": "andriy.moroz@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Катерина Олегівна Лисенко",
        "email": "kateryna.lysenko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Василь Дмитрович Кравченко",
        "email": "vasyl.kravchenko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Наталія Юріївна Шевченко",
        "email": "natalia.shevchenko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Дмитро Сергійович Франко",
        "email": "dmytro.franko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Ірина Олексіївна Савченко",
        "email": "iryna.savchenko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Сергій Михайлович Бойко",
        "email": "serhiy.boyko@teacher.zephyra.edu.ua",
    },
    {
        "full_name": "Оксана Павлівна Ткаченко",
        "email": "oksana.tkachenko@teacher.zephyra.edu.ua",
    },
]

# ── Students (40, 10 per group) ───────────────────────────────────────────────
# email домен @student.zephyra.edu.ua — пароль = частина до @
STUDENTS_DATA = [
    # КН-41 (idx 0-9)
    {
        "full_name": "Олексій Вікторович Мельник",
        "email": "oleksiy.melnyk@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    {
        "full_name": "Анна Романівна Коваль",
        "email": "anna.koval@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    {
        "full_name": "Богдан Андрійович Герасименко",
        "email": "bohdan.gerasymenko@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    {
        "full_name": "Вікторія Сергіївна Власенко",
        "email": "viktoria.vlasenko@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    {
        "full_name": "Григорій Іванович Назаренко",
        "email": "hryhoriy.nazarenko@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    {
        "full_name": "Дарина Михайлівна Пономаренко",
        "email": "daryna.ponomarenko@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    {
        "full_name": "Євген Олегович Романенко",
        "email": "yevhen.romanenko@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    {
        "full_name": "Зоя Дмитрівна Марченко",
        "email": "zoya.marchenko@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    {
        "full_name": "Ігор Васильович Тимченко",
        "email": "ihor.tymchenko@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    {
        "full_name": "Катерина Юріївна Федоренко",
        "email": "kateryna.fedorenko@student.zephyra.edu.ua",
        "group": "КН-41",
    },
    # КН-42 (idx 0-9)
    {
        "full_name": "Леонід Олексійович Гриценко",
        "email": "leonid.grytsenko@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    {
        "full_name": "Марина Петрівна Кириленко",
        "email": "maryna.kyrylenko@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    {
        "full_name": "Назар Богданович Луценко",
        "email": "nazar.lutsenko@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    {
        "full_name": "Оксана Василівна Момот",
        "email": "oksana.momot@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    {
        "full_name": "Павло Андрійович Лазаренко",
        "email": "pavlo.lazarenko@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    {
        "full_name": "Роксолана Ігорівна Яковенко",
        "email": "roksolana.yakovenko@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    {
        "full_name": "Степан Михайлович Данченко",
        "email": "stepan.danchenko@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    {
        "full_name": "Тетяна Олегівна Карпенко",
        "email": "tetyana.karpenko@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    {
        "full_name": "Юрій Дмитрович Семенченко",
        "email": "yuriy.semenchenko@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    {
        "full_name": "Ярослава Сергіївна Захаренко",
        "email": "yaroslava.zakharenko@student.zephyra.edu.ua",
        "group": "КН-42",
    },
    # КН-21 (idx 0-9)
    {
        "full_name": "Артем Олексійович Білоус",
        "email": "artem.bilous@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    {
        "full_name": "Валерія Андріївна Чорна",
        "email": "valeria.chorna@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    {
        "full_name": "Владислав Ігорович Орел",
        "email": "vladyslav.orel@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    {
        "full_name": "Галина Василівна Хоменко",
        "email": "halyna.khomenko@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    {
        "full_name": "Давид Сергійович Олійник",
        "email": "davyd.oliynyk@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    {
        "full_name": "Єлизавета Миколаївна Войтенко",
        "email": "yelyzaveta.voytenko@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    {
        "full_name": "Жанна Ростиславівна Гладченко",
        "email": "zhanna.hladchenko@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    {
        "full_name": "Іванна Тарасівна Супруненко",
        "email": "ivanna.suprunenko@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    {
        "full_name": "Кирило Вікторович Стець",
        "email": "kyrylo.stets@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    {
        "full_name": "Людмила Олегівна Приходько",
        "email": "lyudmyla.prykhodko@student.zephyra.edu.ua",
        "group": "КН-21",
    },
    # КН-22 (idx 0-9)
    {
        "full_name": "Максим Юрійович Гончаренко",
        "email": "maksym.goncharenko@student.zephyra.edu.ua",
        "group": "КН-22",
    },
    {
        "full_name": "Надія Петрівна Бондар",
        "email": "nadiya.bondar@student.zephyra.edu.ua",
        "group": "КН-22",
    },
    {
        "full_name": "Олег Богданович Приймак",
        "email": "oleg.pryymak@student.zephyra.edu.ua",
        "group": "КН-22",
    },
    {
        "full_name": "Поліна Андріївна Рибак",
        "email": "polina.rybak@student.zephyra.edu.ua",
        "group": "КН-22",
    },
    {
        "full_name": "Руслан Дмитрович Гавриленко",
        "email": "ruslan.havrylenko@student.zephyra.edu.ua",
        "group": "КН-22",
    },
    {
        "full_name": "Світлана Сергіївна Тарасенко",
        "email": "svitlana.tarasenko@student.zephyra.edu.ua",
        "group": "КН-22",
    },
    {
        "full_name": "Тимур Олексійович Пилипенко",
        "email": "tymur.pylypenko@student.zephyra.edu.ua",
        "group": "КН-22",
    },
    {
        "full_name": "Уляна Іванівна Костенко",
        "email": "ulyana.kostenko@student.zephyra.edu.ua",
        "group": "КН-22",
    },
    {
        "full_name": "Федір Васильович Яценко",
        "email": "fedir.yatsenko@student.zephyra.edu.ua",
        "group": "КН-22",
    },
    {
        "full_name": "Христина Андріївна Лук'яненко",
        "email": "khrystyna.lukyanenko@student.zephyra.edu.ua",
        "group": "КН-22",
    },
]

# ── Teaching assignments ──────────────────────────────────────────────────────
# (teacher_email_prefix, subject_name, group_name)
TEACHING_ASSIGNMENTS_DATA = [
    # КН-41 — 4-й курс, поглиблені предмети (8 предметів)
    ("ivan.kovalenko", "Алгоритми та структури даних", "КН-41"),
    ("olena.petrenko", "Об'єктно-орієнтоване програмування", "КН-41"),
    ("mykola.sydorenko", "Бази даних", "КН-41"),
    ("yulia.bondarenko", "Комп'ютерні мережі", "КН-41"),
    ("yulia.bondarenko", "Безпека інформаційних систем", "КН-41"),
    ("vasyl.kravchenko", "Штучний інтелект та МН", "КН-41"),
    ("vasyl.kravchenko", "Мобільна розробка", "КН-41"),
    ("dmytro.franko", "Веб-технології", "КН-41"),
    # КН-42 — 4-й курс, поглиблені предмети (8 предметів)
    ("ivan.kovalenko", "Алгоритми та структури даних", "КН-42"),
    ("olena.petrenko", "Програмування мовою Python", "КН-42"),
    ("mykola.sydorenko", "Бази даних", "КН-42"),
    ("yulia.bondarenko", "Комп'ютерні мережі", "КН-42"),
    ("yulia.bondarenko", "Безпека інформаційних систем", "КН-42"),
    ("vasyl.kravchenko", "Штучний інтелект та МН", "КН-42"),
    ("vasyl.kravchenko", "Мобільна розробка", "КН-42"),
    ("andriy.moroz", "Системне програмування", "КН-42"),
    # КН-21 — 2-й курс, фундаментальні предмети (7 предметів)
    ("ivan.kovalenko", "Вища математика", "КН-21"),
    ("olena.petrenko", "Об'єктно-орієнтоване програмування", "КН-21"),
    ("kateryna.lysenko", "Дискретна математика", "КН-21"),
    ("kateryna.lysenko", "Теорія ймовірностей та статистика", "КН-21"),
    ("oksana.tkachenko", "Бази даних", "КН-21"),
    ("serhiy.boyko", "Програмування мовою Python", "КН-21"),
    ("dmytro.franko", "Веб-технології", "КН-21"),
    # КН-22 — 2-й курс, фундаментальні предмети (7 предметів)
    ("ivan.kovalenko", "Вища математика", "КН-22"),
    ("kateryna.lysenko", "Дискретна математика", "КН-22"),
    ("kateryna.lysenko", "Теорія ймовірностей та статистика", "КН-22"),
    ("iryna.savchenko", "Алгоритми та структури даних", "КН-22"),
    ("natalia.shevchenko", "Комп'ютерна архітектура", "КН-22"),
    ("andriy.moroz", "Операційні системи", "КН-22"),
    ("serhiy.boyko", "Програмування мовою Python", "КН-22"),
]

# ── Schedule: (day_of_week, lesson_number) per group ─────────────────────────
# unique_together на ScheduleTemplate: (group, day_of_week, lesson_number)
GROUP_SCHEDULE_SLOTS = {
    "КН-41": [
        (1, 1),
        (1, 2),
        (1, 3),
        (2, 1),
        (2, 2),
        (2, 3),
        (2, 4),
        (3, 1),
        (3, 2),
        (3, 3),
        (4, 1),
        (4, 2),
        (4, 3),
        (4, 4),
        (5, 1),
        (5, 2),
        (5, 3),
    ],
    "КН-42": [
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
        (2, 1),
        (2, 2),
        (2, 3),
        (3, 1),
        (3, 2),
        (3, 3),
        (3, 4),
        (4, 1),
        (4, 2),
        (4, 3),
        (5, 1),
        (5, 2),
    ],
    "КН-21": [
        (1, 1),
        (1, 2),
        (1, 3),
        (2, 1),
        (2, 2),
        (3, 1),
        (3, 2),
        (3, 3),
        (4, 1),
        (4, 2),
        (4, 3),
        (5, 1),
        (5, 2),
    ],
    "КН-22": [
        (1, 1),
        (1, 2),
        (1, 3),
        (2, 2),
        (2, 3),
        (2, 4),
        (3, 1),
        (3, 2),
        (3, 3),
        (4, 2),
        (4, 3),
        (4, 4),
        (5, 1),
        (5, 2),
    ],
}

# ── Topics per subject ────────────────────────────────────────────────────────
TOPICS = {
    "Вища математика": [
        "Визначений інтеграл та його застосування",
        "Невизначений інтеграл. Методи інтегрування",
        "Диференціальні рівняння першого порядку",
        "Числові ряди. Ознаки збіжності",
        "Функції кількох змінних. Часткові похідні",
        "Подвійний інтеграл та його застосування",
    ],
    "Об'єктно-орієнтоване програмування": [
        "Інкапсуляція, наслідування, поліморфізм",
        "Патерни проектування: Singleton, Factory, Observer",
        "Абстрактні класи та інтерфейси",
        "Виняткові ситуації та їх обробка",
        "SOLID-принципи проектування",
        "Рефакторинг коду. Code Smells",
    ],
    "Бази даних": [
        "Реляційна модель даних. Нормальні форми",
        "SQL: складні запити, підзапити, JOIN",
        "Транзакції та рівні ізоляції",
        "Індекси та оптимізація запитів",
        "Збережені процедури та тригери",
        "NoSQL-бази даних: MongoDB, Redis",
    ],
    "Веб-технології": [
        "HTTP/HTTPS протокол. REST API",
        "JavaScript: асинхронність, Promise, async/await",
        "React: компоненти, хуки, стан",
        "Django: моделі, представлення, шаблони",
        "Автентифікація та авторизація у веб-додатках",
        "WebSockets та реал-тайм комунікація",
    ],
    "Алгоритми та структури даних": [
        "Сортування: merge sort, quick sort, heap sort",
        "Бінарні дерева пошуку. AVL-дерева",
        "Графи: алгоритми BFS та DFS",
        "Алгоритм Дейкстри та A*",
        "Динамічне програмування",
        "Хеш-таблиці. Методи вирішення колізій",
    ],
    "Комп'ютерні мережі": [
        "Модель OSI та стек протоколів TCP/IP",
        "Мережевий рівень. IP-адресація та маршрутизація",
        "Транспортний рівень. TCP vs UDP",
        "DNS, DHCP, NAT",
        "Мережева безпека. Брандмауери та VPN",
        "Бездротові мережі: Wi-Fi стандарти",
    ],
    "Комп'ютерна архітектура": [
        "Архітектура процесора. Конвеєризація",
        "Пам'ять: ієрархія, кеш, віртуальна пам'ять",
        "Паралелізм на рівні інструкцій",
        "Багатоядерні процесори. SIMD",
        "Архітектура GPU",
        "Введення/Виведення. Переривання",
    ],
    "Операційні системи": [
        "Управління процесами та потоками",
        "Синхронізація: м'ютекси, семафори, монітори",
        "Управління пам'яттю. Сторінкова організація",
        "Файлові системи: FAT, NTFS, ext4",
        "Планування процесів: FCFS, SJF, Round Robin",
        "Deadlock: умови виникнення та методи запобігання",
    ],
    "Дискретна математика": [
        "Теорія множин. Відношення та функції",
        "Математична логіка. Нормальні форми",
        "Теорія графів. Основні поняття та задачі",
        "Комбінаторика: перестановки, розміщення, комбінації",
        "Булева алгебра та логічні схеми",
        "Рекурентні співвідношення",
    ],
    "Програмування мовою Python": [
        "Декоратори та генератори",
        "Об'єктно-орієнтоване програмування в Python",
        "Робота з файлами, JSON, CSV",
        "NumPy та Pandas: основи аналізу даних",
        "Тестування: unittest, pytest",
        "Паралельне програмування: asyncio",
    ],
    "Штучний інтелект та МН": [
        "Машинне навчання: класифікація та регресія",
        "Нейронні мережі: перцептрон та багатошарові мережі",
        "Згорткові нейронні мережі (CNN)",
        "Рекурентні нейронні мережі (RNN, LSTM)",
        "Навчання з підкріпленням",
        "Трансформери та Attention Mechanism",
    ],
    "Мобільна розробка": [
        "Архітектура мобільних додатків",
        "Flutter: основи та State Management",
        "Нативний Android: Kotlin основи",
        "iOS розробка: Swift та SwiftUI",
        "Робота з API та локальним сховищем",
        "Push-сповіщення та фонові задачі",
    ],
    "Безпека інформаційних систем": [
        "Криптографія: симетричне та асиметричне шифрування",
        "Атаки на веб-додатки: XSS, SQL Injection, CSRF",
        "PKI та цифровий підпис",
        "Аутентифікація: паролі, MFA, OAuth 2.0",
        "OWASP Top 10: огляд вразливостей",
        "Пентестинг: методологія та інструменти",
    ],
    "Теорія ймовірностей та статистика": [
        "Ймовірнісний простір. Аксіоми Колмогорова",
        "Умовна ймовірність. Формула Байєса",
        "Випадкові величини та їх розподіли",
        "Математичне очікування та дисперсія",
        "Закон великих чисел",
        "Центральна гранична теорема",
    ],
    "Системне програмування": [
        "Системні виклики POSIX: процеси",
        "Міжпроцесна взаємодія: pipes, FIFO",
        "Сокети та мережеве програмування",
        "Потоки (pthreads) та синхронізація",
        "Сигнали в Unix/Linux",
        "Динамічне завантаження бібліотек",
    ],
}
DEFAULT_TOPICS = [
    "Введення в тему. Основні поняття",
    "Теоретичні основи розділу",
    "Практичне застосування теорії",
    "Розбір типових задач та прикладів",
    "Узагальнення та систематизація знань",
]

CANCELLATION_REASONS = [
    "Викладач на лікарняному",
    "Позапланові збори кафедри",
    "Адміністративний захід університету",
    "Державне свято (перенесення)",
]

# ── Student grade profiles (index in group, 0-based) ─────────────────────────
# (profile_label, grade_weights[1..12], absence_probability)
STUDENT_PROFILES = {
    0: ("відмінник", [0, 0, 0, 0, 0, 0, 1, 2, 5, 8, 12, 12], 0.03),
    1: ("відмінник", [0, 0, 0, 0, 0, 0, 1, 2, 5, 8, 12, 12], 0.03),
    2: ("хорошист", [0, 0, 0, 0, 1, 2, 4, 8, 10, 8, 4, 2], 0.07),
    3: ("хорошист", [0, 0, 0, 0, 1, 2, 4, 8, 10, 8, 4, 2], 0.07),
    4: ("хорошист", [0, 0, 0, 0, 1, 2, 4, 8, 10, 8, 4, 2], 0.07),
    5: ("середняк", [1, 2, 3, 5, 8, 10, 8, 5, 3, 2, 1, 0], 0.10),
    6: ("середняк", [1, 2, 3, 5, 8, 10, 8, 5, 3, 2, 1, 0], 0.10),
    7: ("середняк", [1, 2, 3, 5, 8, 10, 8, 5, 3, 2, 1, 0], 0.10),
    8: ("двієчник", [8, 10, 10, 8, 5, 3, 2, 1, 1, 0, 0, 0], 0.15),
    9: ("прогульник", [1, 2, 3, 4, 6, 8, 8, 5, 3, 2, 1, 1], 0.40),
}

COMMENTS_POOL = [
    "Відмінна робота, продовжуйте в тому ж дусі!",
    "Є незначні помилки, потрібно доопрацювати.",
    "Гарний результат, але можна краще.",
    "Завдання виконано не в повному обсязі.",
    "Проявили творчий підхід до розв'язання.",
    "Потрібно повторити теоретичний матеріал.",
    "Відмінне розуміння теми!",
    "Зверніть увагу на оформлення роботи.",
    "Бонус за активну роботу на занятті.",
    "Потрібно прийти на консультацію.",
]


class Command(BaseCommand):
    help = (
        "Очищає БД (крім суперадміна) і заповнює: "
        "40 студентів / 12 викладачів / 15 предметів / уроки за 3 тижні / оцінки."
    )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("=" * 65))
        self.stdout.write(self.style.WARNING("  RESET AND SEED — Zephyra EduTrack"))
        self.stdout.write(self.style.WARNING(f"  Сьогодні: {TODAY}"))
        self.stdout.write(
            self.style.WARNING(
                f"  Діапазон: {START_DATE} → {END_DATE}  |  Оцінки до: {GRADES_CUTOFF}"
            )
        )
        self.stdout.write(self.style.WARNING("=" * 65))

        absence_reasons = self._step1_clear_and_static()
        groups = self._step2_groups()
        teachers = self._step3_teachers()
        students_by_group = self._step4_students(groups)
        tas = self._step5_teaching_assignments(teachers, groups)
        self._step6_evaluation_types(tas)
        group_templates = self._step7_schedule_templates(tas, groups)
        self._step8_lessons(group_templates, tas)
        self._step9_grades(absence_reasons, students_by_group)

        self._print_summary(groups, teachers, students_by_group)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: очищення + статичні довідники
    # ─────────────────────────────────────────────────────────────────────────
    def _step1_clear_and_static(self):
        self.stdout.write("\n[1/9] Clearing data (superadmin preserved)...")

        # Видалення у правильному порядку залежностей
        BuildingAccessLog.objects.all().delete()
        Notification.objects.all().delete()
        Comment.objects.all().delete()
        Post.objects.all().delete()
        StudentPerformance.objects.all().delete()
        Lesson.objects.all().delete()
        ScheduleTemplate.objects.all().delete()
        EvaluationType.objects.all().delete()
        TeachingAssignment.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        StudyGroup.objects.all().delete()
        Subject.objects.all().delete()
        Classroom.objects.all().delete()
        AbsenceReason.objects.all().delete()

        self.stdout.write("  Дані очищені.")

        for d in CLASSROOMS_DATA:
            Classroom.objects.create(**d)
        self.stdout.write(f"  Аудиторій: {len(CLASSROOMS_DATA)}")

        for d in SUBJECTS_DATA:
            Subject.objects.create(**d)
        self.stdout.write(f"  Предметів: {len(SUBJECTS_DATA)}")

        absence_reasons = {}
        for d in ABSENCE_REASONS_DATA:
            ar = AbsenceReason.objects.create(**d)
            absence_reasons[ar.code] = ar
        self.stdout.write(f"  Причин пропусків: {len(absence_reasons)}")

        self.stdout.write(self.style.SUCCESS("  OK"))
        return absence_reasons

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: групи
    # ─────────────────────────────────────────────────────────────────────────
    def _step2_groups(self):
        self.stdout.write("\n[2/9] Creating groups...")
        groups = {}
        for d in GROUPS_DATA:
            g = StudyGroup.objects.create(**d)
            groups[g.name] = g
        self.stdout.write(f"  Групи: {', '.join(groups)}")
        self.stdout.write(self.style.SUCCESS("  OK"))
        return groups

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: викладачі
    # ─────────────────────────────────────────────────────────────────────────
    def _step3_teachers(self):
        self.stdout.write("\n[3/9] Creating teachers...")
        teachers = {}
        for d in TEACHERS_DATA:
            email = d["email"]
            password = email.split("@")[0]
            teacher = User.objects.create_user(
                email=email,
                password=password,
                full_name=d["full_name"],
                role="teacher",
                is_staff=True,
            )
            teachers[password] = teacher  # key = email prefix
        self.stdout.write(f"  Викладачів: {len(teachers)}")
        self.stdout.write(self.style.SUCCESS("  OK"))
        return teachers

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: студенти
    # ─────────────────────────────────────────────────────────────────────────
    def _step4_students(self, groups):
        self.stdout.write("\n[4/9] Creating students...")
        students_by_group = {name: [] for name in groups}
        counters = {name: 0 for name in groups}

        for d in STUDENTS_DATA:
            email = d["email"]
            password = email.split("@")[0]
            gname = d["group"]
            group = groups[gname]
            idx = counters[gname]
            counters[gname] += 1

            student = User.objects.create_user(
                email=email,
                password=password,
                full_name=d["full_name"],
                role="student",
                group=group,
                student_id=f"STU-{group.year_of_entry}-{idx + 1:03d}",
            )
            students_by_group[gname].append(student)

        total = sum(len(v) for v in students_by_group.values())
        self.stdout.write(
            f"  Студентів: {total}  ({', '.join(f'{k}:{len(v)}' for k,v in students_by_group.items())})"
        )
        self.stdout.write(self.style.SUCCESS("  OK"))
        return students_by_group

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: teaching assignments
    # ─────────────────────────────────────────────────────────────────────────
    def _step5_teaching_assignments(self, teachers, groups):
        self.stdout.write("\n[5/9] Creating teaching assignments...")
        subject_map = {s.name: s for s in Subject.objects.all()}
        tas = []

        for teacher_prefix, subject_name, group_name in TEACHING_ASSIGNMENTS_DATA:
            teacher = teachers.get(teacher_prefix)
            subject = subject_map.get(subject_name)
            group = groups.get(group_name)

            if not all([teacher, subject, group]):
                self.stdout.write(
                    self.style.ERROR(
                        f"  SKIP: teacher={teacher_prefix}, subject={subject_name}, group={group_name}"
                    )
                )
                continue

            ta = TeachingAssignment.objects.create(
                subject=subject,
                teacher=teacher,
                group=group,
                academic_year="2025/2026",
                semester=2,
                start_date=START_DATE,
                end_date=END_DATE,
                is_active=True,
            )
            tas.append(ta)

        self.stdout.write(f"  Teaching assignments: {len(tas)}")
        self.stdout.write(self.style.SUCCESS("  OK"))
        return tas

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: evaluation types (Лекція/Практика/Лабораторна для кожного TA)
    # ─────────────────────────────────────────────────────────────────────────
    def _step6_evaluation_types(self, tas):
        self.stdout.write("\n[6/9] Creating evaluation types...")
        et_data = [
            ("Лекція", Decimal("50.00"), 1),
            ("Практика", Decimal("30.00"), 2),
            ("Лабораторна", Decimal("20.00"), 3),
        ]
        for ta in tas:
            for name, weight, order in et_data:
                EvaluationType.objects.create(
                    assignment=ta, name=name, weight_percent=weight, order=order
                )
        self.stdout.write(f"  EvaluationTypes: {len(tas) * 3}")
        self.stdout.write(self.style.SUCCESS("  OK"))

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: schedule templates
    # ─────────────────────────────────────────────────────────────────────────
    def _step7_schedule_templates(self, tas, groups):
        self.stdout.write("\n[7/9] Creating schedule templates...")
        classrooms = list(Classroom.objects.filter(is_active=True))

        group_ta_map = {}
        for ta in tas:
            group_ta_map.setdefault(ta.group.name, []).append(ta)

        group_templates = {}
        for group_name, slots in GROUP_SCHEDULE_SLOTS.items():
            group_obj = groups[group_name]
            group_tas = group_ta_map.get(group_name, [])
            if not group_tas:
                continue

            tmpl_list = []
            for i, (day, lesson_num) in enumerate(slots):
                ta = group_tas[i % len(group_tas)]
                start_t, end_t = TIME_MAP[lesson_num]
                duration = (end_t.hour * 60 + end_t.minute) - (
                    start_t.hour * 60 + start_t.minute
                )
                classroom = random.choice(classrooms) if classrooms else None

                try:
                    tmpl = ScheduleTemplate.objects.create(
                        group=group_obj,
                        subject=ta.subject,
                        teacher=ta.teacher,
                        teaching_assignment=ta,
                        day_of_week=day,
                        lesson_number=lesson_num,
                        start_time=start_t,
                        duration_minutes=duration,
                        classroom=classroom,
                        is_active=True,
                    )
                    tmpl_list.append((tmpl, ta))
                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  Template ERR {group_name} day={day} slot={lesson_num}: {exc}"
                        )
                    )

            group_templates[group_name] = tmpl_list
            self.stdout.write(f"  {group_name}: {len(tmpl_list)} templates")

        self.stdout.write(self.style.SUCCESS("  OK"))
        return group_templates

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: уроки (3 тижні)
    # ─────────────────────────────────────────────────────────────────────────
    def _step8_lessons(self, group_templates, tas):
        self.stdout.write("\n[8/9] Creating lessons...")

        # Будуємо швидкий lookup: ta.id -> {type: EvaluationType}
        ta_et = {}
        for ta in tas:
            ets = {et.name: et for et in ta.evaluation_types.all()}
            ta_et[ta.id] = {
                "lecture": ets.get("Лекція"),
                "practical": ets.get("Практика"),
                "lab": ets.get("Лабораторна"),
            }

        topic_counters = {}
        type_counters = {}
        lessons_batch = []

        current = START_DATE
        while current <= END_DATE:
            dow = current.isoweekday()  # 1=Пн … 7=Нд
            if dow <= 5:
                for group_name, tmpl_list in group_templates.items():
                    for tmpl, ta in tmpl_list:
                        if tmpl.day_of_week != dow:
                            continue

                        key = (ta.group_id, ta.subject_id)
                        topic_list = TOPICS.get(ta.subject.name, DEFAULT_TOPICS)
                        t_idx = topic_counters.get(key, 0)
                        topic = topic_list[t_idx % len(topic_list)]
                        topic_counters[key] = t_idx + 1

                        l_idx = type_counters.get(key, 0)
                        lesson_type = LESSON_TYPE_CYCLE[l_idx % len(LESSON_TYPE_CYCLE)]
                        type_counters[key] = l_idx + 1

                        eval_type = ta_et.get(ta.id, {}).get(lesson_type)
                        start_t, end_t = TIME_MAP[tmpl.lesson_number]

                        # Скасовані уроки: 2% минулих, 5% майбутніх
                        is_cancelled = False
                        cancel_reason = ""
                        threshold = 0.05 if current > TODAY else 0.02
                        if random.random() < threshold:
                            is_cancelled = True
                            cancel_reason = random.choice(CANCELLATION_REASONS)

                        lessons_batch.append(
                            Lesson(
                                group=ta.group,
                                subject=ta.subject,
                                teacher=ta.teacher,
                                date=current,
                                start_time=start_t,
                                end_time=end_t,
                                topic=topic,
                                classroom=tmpl.classroom,
                                max_points=12,
                                evaluation_type=eval_type,
                                template_source=tmpl,
                                is_cancelled=is_cancelled,
                                cancellation_reason=cancel_reason,
                            )
                        )

            current += timedelta(days=1)

        created = Lesson.objects.bulk_create(lessons_batch, ignore_conflicts=True)
        self.stdout.write(
            f"  Уроків створено: {len(created)}  ({START_DATE} → {END_DATE})"
        )
        cancelled = sum(1 for l in lessons_batch if l.is_cancelled)
        self.stdout.write(f"  З них скасованих: {cancelled}")
        self.stdout.write(self.style.SUCCESS("  OK"))

    # ─────────────────────────────────────────────────────────────────────────
    # Step 9: оцінки + пропуски
    # ─────────────────────────────────────────────────────────────────────────
    def _step9_grades(self, absence_reasons, students_by_group):
        self.stdout.write(f"\n[9/9] Creating grades + absences (до {GRADES_CUTOFF})...")

        lessons = list(
            Lesson.objects.filter(
                date__gte=START_DATE,
                date__lte=GRADES_CUTOFF,
                is_cancelled=False,
            ).select_related("group", "subject", "teacher")
        )

        all_absence = list(absence_reasons.values())
        excused = [ar for ar in all_absence if ar.is_respectful]
        unexcused = absence_reasons.get("Н", all_absence[0])

        perf_batch = []
        total_absent = 0
        total_bonus = 0

        for lesson in lessons:
            students = students_by_group.get(lesson.group.name, [])
            graded_by = lesson.teacher
            grade_hour = min(lesson.start_time.hour + 1, 23)
            graded_at = timezone.make_aware(
                datetime.combine(lesson.date, time(grade_hour, 30))
            )

            for idx, student in enumerate(students):
                profile, weights, absence_prob = STUDENT_PROFILES.get(
                    idx % 10, STUDENT_PROFILES[5]
                )

                if random.random() < absence_prob:
                    # ── Пропуск ──────────────────────────────────────────────
                    if idx % 10 == 8:
                        # двієчник — 70% неповажних
                        ar = (
                            unexcused
                            if random.random() < 0.7
                            else random.choice(excused or [unexcused])
                        )
                    elif idx % 10 == 9:
                        # прогульник — рівномірно всі типи
                        ar = random.choice(all_absence)
                    else:
                        # решта — переважно поважні
                        ar = (
                            random.choice(excused)
                            if excused and random.random() < 0.7
                            else unexcused
                        )

                    perf_batch.append(
                        StudentPerformance(
                            lesson=lesson,
                            student=student,
                            absence=ar,
                            earned_points=None,
                            comment=(
                                random.choice(COMMENTS_POOL)
                                if random.random() < 0.25
                                else ""
                            ),
                            graded_by=graded_by,
                            graded_at=graded_at,
                        )
                    )
                    total_absent += 1

                else:
                    # ── Оцінка ───────────────────────────────────────────────
                    pts = random.choices(range(1, 13), weights=weights)[0]
                    is_bonus = random.random() < 0.05
                    comment = (
                        random.choice(COMMENTS_POOL) if random.random() < 0.12 else ""
                    )
                    if is_bonus:
                        comment = "Бонус за активну роботу на занятті."
                        total_bonus += 1

                    perf_batch.append(
                        StudentPerformance(
                            lesson=lesson,
                            student=student,
                            absence=None,
                            earned_points=pts,
                            is_bonus=is_bonus,
                            comment=comment,
                            graded_by=graded_by,
                            graded_at=graded_at,
                            version=1,
                        )
                    )

        StudentPerformance.objects.bulk_create(perf_batch, ignore_conflicts=True)
        self.stdout.write(
            f"  Записів: {len(perf_batch)}  |  Пропусків: {total_absent}  |  Бонусів: {total_bonus}"
        )
        self.stdout.write(self.style.SUCCESS("  OK"))

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────
    def _print_summary(self, groups, teachers, students_by_group):
        self.stdout.write("\n" + "─" * 65)
        self.stdout.write(self.style.SUCCESS("ПІДСУМОК SEED"))
        self.stdout.write("─" * 65)
        self.stdout.write(f"  Груп:      {StudyGroup.objects.count()}")
        self.stdout.write(f"  Викладачів:{len(teachers)}")
        self.stdout.write(
            f"  Студентів: {sum(len(v) for v in students_by_group.values())}"
        )
        self.stdout.write(f"  Предметів: {Subject.objects.count()}")
        self.stdout.write(
            f"  Уроків:    {Lesson.objects.count()}  (з них скасованих: {Lesson.objects.filter(is_cancelled=True).count()})"
        )
        self.stdout.write(f"  Оцінок/Пропусків: {StudentPerformance.objects.count()}")
        self.stdout.write("")
        self.stdout.write("ЛОГІН / ПАРОЛЬ:")
        self.stdout.write("  Суперадмін: (не змінено)")
        self.stdout.write(
            "  Викладач:   ivan.kovalenko@teacher.zephyra.edu.ua  /  ivan.kovalenko"
        )
        self.stdout.write(
            "  Студент:    anna.koval@student.zephyra.edu.ua      /  anna.koval"
        )
        self.stdout.write("")
        self.stdout.write("ПРОФІЛІ СТУДЕНТІВ (позиція у групі):")
        self.stdout.write(
            "  0,1  — відмінник  |  2,3,4 — хорошист  |  5,6,7 — середняк"
        )
        self.stdout.write("  8    — двієчник   |  9     — прогульник")
        self.stdout.write("─" * 65)
