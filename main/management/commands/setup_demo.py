"""
Management command: setup_demo

Creates (or recreates) the isolated demo.db SQLite database with realistic
seed data. Does NOT touch the production database in any way.

Usage:
    python manage.py setup_demo

Demo credentials:
    Admin   : demo_admin@mentorly.app   / demo1234
    Teacher : ivan.demo@teacher.app     / ivan.demo
    Student : anna.demo@student.app     / anna.demo
"""

import random
from datetime import date, time, timedelta

from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand

from main.models import (
    AbsenceReason,
    Classroom,
    EvaluationType,
    InstitutionSettings,
    Lesson,
    Specialty,
    StudentPerformance,
    StudyGroup,
    Subject,
    TeachingAssignment,
    TimeSlot,
    User,
)

DB = "demo"

TODAY = date.today()
THIS_MON = TODAY - timedelta(days=TODAY.weekday())
PREV_MON = THIS_MON - timedelta(weeks=1)


def _save(obj):
    """Save a model instance explicitly to the demo DB."""
    obj.save(using=DB)
    return obj


def _create(Model, **kwargs):
    obj = Model(**kwargs)
    obj.save(using=DB)
    return obj


def _make_user(email, full_name, role, password, **extra):
    u = User(email=email, full_name=full_name, role=role,
              is_active=True, is_staff=(role in ("admin", "teacher")), **extra)
    u.password = make_password(password)
    u.save(using=DB)
    return u


class Command(BaseCommand):
    help = "Builds the isolated demo.db SQLite database with seed data."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("=" * 60))
        self.stdout.write(self.style.WARNING("  setup_demo — isolated demo.db"))
        self.stdout.write(self.style.WARNING("=" * 60))

        self._migrate()
        self._clear()
        self._seed()

        self.stdout.write(self.style.SUCCESS("\nDemo DB ready."))
        self.stdout.write("  Admin   : demo_admin@mentorly.app  /  demo1234")
        self.stdout.write("  Teacher : ivan.demo@teacher.app    /  ivan.demo")
        self.stdout.write("  Student : anna.demo@student.app    /  anna.demo")

    # ── Step 1 ────────────────────────────────────────────────────────────────

    def _migrate(self):
        self.stdout.write("\n[1/3] Running migrations on demo DB...")
        call_command("migrate", database=DB, verbosity=0, run_syncdb=True)
        self.stdout.write(self.style.SUCCESS("  OK"))

    # ── Step 2 ────────────────────────────────────────────────────────────────

    def _clear(self):
        self.stdout.write("\n[2/3] Clearing old demo data...")
        for Model in [
            StudentPerformance, Lesson, EvaluationType,
            TeachingAssignment, User, StudyGroup, Subject,
            Classroom, AbsenceReason, Specialty, TimeSlot,
        ]:
            Model.objects.using(DB).all().delete()
        InstitutionSettings.objects.using(DB).all().delete()
        self.stdout.write(self.style.SUCCESS("  OK"))

    # ── Step 3 ────────────────────────────────────────────────────────────────

    def _seed(self):
        self.stdout.write("\n[3/3] Seeding demo data...")
        random.seed(7)

        # Institution
        _create(InstitutionSettings,
                name="Mentorly Demo",
                tagline="Демонстраційна версія · зміни не зберігаються")

        # Specialty
        spec = _create(Specialty, name="Інженерія програмного забезпечення",
                       code="121", is_active=True)

        # Groups
        g1 = _create(StudyGroup, name="КН-41", year_of_entry=2023,
                     graduation_year=2027, specialty=spec, course=2)
        g2 = _create(StudyGroup, name="КН-42", year_of_entry=2023,
                     graduation_year=2027, specialty=spec, course=2)

        # Time slots
        for num, name, s, e in [
            (1, "1-а пара", time(8, 0),  time(8, 50)),
            (2, "2-а пара", time(9, 0),  time(9, 50)),
            (3, "3-а пара", time(10, 0), time(10, 50)),
            (4, "4-а пара", time(12, 0), time(12, 50)),
            (5, "5-а пара", time(13, 0), time(13, 50)),
        ]:
            _create(TimeSlot, lesson_number=num, name=name,
                    start_time=s, end_time=e)

        # Absence reasons
        ar_n = _create(AbsenceReason, code="Н",
                       description="Без поважної причини",
                       is_respectful=False, color="#e74c3c", order=1)
        _create(AbsenceReason, code="Б", description="Хвороба",
                is_respectful=True, color="#3498db", order=2)
        _create(AbsenceReason, code="ПП", description="Поважна причина",
                is_respectful=True, color="#2ecc71", order=3)

        # Classrooms
        r1 = _create(Classroom, name="101", building="Корпус А",
                     floor=1, capacity=30, type="lecture")
        r2 = _create(Classroom, name="305", building="Корпус А",
                     floor=3, capacity=20, type="computer")

        # Subjects
        subj1 = _create(Subject, name="Веб-технології",
                        code="WEB-301", credits=4, hours_total=120, semester=3)
        subj2 = _create(Subject, name="Бази даних",
                        code="DB-202", credits=4, hours_total=120, semester=3)
        subj3 = _create(Subject, name="Алгоритми та структури даних",
                        code="ASD-203", credits=5, hours_total=150, semester=3)
        subj4 = _create(Subject, name="Об'єктно-орієнтоване програмування",
                        code="OOP-201", credits=4, hours_total=120, semester=3)
        subj5 = _create(Subject, name="Вища математика",
                        code="MATH-101", credits=5, hours_total=150, semester=1)

        # Admin
        _make_user("demo_admin@mentorly.app", "Демо Адміністратор",
                   "admin", "demo1234")

        # Teachers
        t1 = _make_user("ivan.demo@teacher.app",    "Іван Коваленко",   "teacher", "ivan.demo")
        t2 = _make_user("olena.demo@teacher.app",   "Олена Петренко",   "teacher", "olena.demo")
        t3 = _make_user("mykola.demo@teacher.app",  "Микола Сидоренко", "teacher", "mykola.demo")
        t4 = _make_user("yulia.demo@teacher.app",   "Юлія Бондаренко",  "teacher", "yulia.demo")

        # Students — group КН-41
        STUDENTS_G1 = [
            ("Анна Коваль",       "anna.demo"),
            ("Богдан Мельник",    "bohdan.demo"),
            ("Вікторія Шевченко", "viktoria.demo"),
            ("Григорій Бондаренко", "hryhoriy.demo"),
            ("Дарина Ткаченко",   "daryna.demo"),
            ("Євген Марченко",    "yevhen.demo"),
            ("Жанна Павленко",    "zhanna.demo"),
            ("Захар Кравченко",   "zakhar.demo"),
        ]
        students1 = []
        for idx, (name, prefix) in enumerate(STUDENTS_G1):
            s = _make_user(f"{prefix}@student.app", name, "student", prefix,
                           group_id=g1.pk,
                           student_id=f"DEMO-41-{idx+1:03d}")
            students1.append(s)

        # Students — group КН-42
        STUDENTS_G2 = [
            ("Ірина Лисенко",    "iryna.demo"),
            ("Кирило Мороз",     "kyrylo.demo"),
            ("Лариса Петренко",  "larysa.demo"),
            ("Михайло Франко",   "mykhailo.demo"),
            ("Наталія Савченко", "natalia.demo"),
            ("Олег Бойко",       "oleh.demo"),
            ("Поліна Ткач",      "polina.demo"),
            ("Роман Гриценко",   "roman.demo"),
        ]
        students2 = []
        for idx, (name, prefix) in enumerate(STUDENTS_G2):
            s = _make_user(f"{prefix}@student.app", name, "student", prefix,
                           group_id=g2.pk,
                           student_id=f"DEMO-42-{idx+1:03d}")
            students2.append(s)

        # Teaching assignments (teacher → subject → group)
        ASSIGNMENTS = [
            (t1, subj1, g1, r1), (t1, subj1, g2, r1),
            (t2, subj2, g1, r2), (t2, subj2, g2, r2),
            (t3, subj3, g1, r1),
            (t4, subj4, g1, r2), (t4, subj4, g2, r2),
        ]
        tas = []
        for teacher, subj, group, room in ASSIGNMENTS:
            ta = _create(TeachingAssignment,
                         subject=subj, teacher=teacher,
                         group=group, academic_year="2024-2025",
                         semester=3, start_date=date(2025, 2, 1),
                         end_date=date(2025, 6, 30))
            ev_lec = _create(EvaluationType, assignment=ta,
                             name="Лекція", weight_percent=30, order=1)
            ev_prc = _create(EvaluationType, assignment=ta,
                             name="Практична", weight_percent=70, order=2)
            tas.append((ta, ev_lec, ev_prc, group, room))

        # Lessons — previous week + current week (Mon–Fri, 3 slots/day)
        lessons = []
        LESSON_SLOTS = [time(9, 0), time(10, 0), time(12, 0)]
        LESSON_ENDS  = [time(9, 50), time(10, 50), time(12, 50)]
        TOPICS = [
            "Вступ. Основні поняття", "Практична робота №1",
            "Теоретичні основи", "Лабораторна робота",
            "Контрольна робота", "Семінар: обговорення",
        ]
        for week_mon in [PREV_MON, THIS_MON]:
            for dow in range(5):
                lesson_date = week_mon + timedelta(days=dow)
                for slot_idx, (ta, ev_lec, ev_prc, group, room) in enumerate(tas[:3]):
                    si = slot_idx % 3
                    ev = ev_lec if slot_idx % 2 == 0 else ev_prc
                    l = _create(Lesson,
                                group=group,
                                subject=ta.subject,
                                teacher=ta.teacher,
                                date=lesson_date,
                                start_time=LESSON_SLOTS[si],
                                end_time=LESSON_ENDS[si],
                                topic=random.choice(TOPICS) + f" ({ta.subject.code})",
                                max_points=12,
                                evaluation_type=ev,
                                is_cancelled=False)
                    lessons.append((l, group))

        # Grades for all past lessons
        for lesson, group in lessons:
            if lesson.date > TODAY:
                continue
            students = students1 if group == g1 else students2
            for stu in students:
                absence_roll = random.random()
                if absence_roll < 0.08:
                    _create(StudentPerformance,
                            lesson=lesson, student=stu,
                            earned_points=None, absence=ar_n)
                else:
                    pts = random.randint(5, 12)
                    _create(StudentPerformance,
                            lesson=lesson, student=stu,
                            earned_points=pts)

        self.stdout.write(
            f"  Groups: 2 | Teachers: 4 | Students: {len(students1)+len(students2)}"
        )
        self.stdout.write(
            f"  Subjects: 5 | Assignments: {len(tas)} | Lessons: {len(lessons)}"
        )
        self.stdout.write(self.style.SUCCESS("  OK"))
