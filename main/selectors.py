"""
Selectors - складні DB запити (read-only)

Цей модуль містить функції для отримання даних з БД.
Використовуйте селектори для складних запитів з join'ами, aggregate, тощо.

Правило: Selectors тільки читають дані, не змінюють їх.
"""

from datetime import date, timedelta
from typing import Optional

from django.db.models import Avg, Count, Prefetch, Q, QuerySet, Sum

from main.models import (
    Lesson,
    ScheduleTemplate,
    StudentPerformance,
    StudyGroup,
    Subject,
    TeachingAssignment,
    User,
)


def get_student_performance_data(
    student: User, filters: Optional[dict] = None
) -> QuerySet[StudentPerformance]:
    """
    Отримання даних успішності студента з фільтрами.

    Args:
        student: Об'єкт студента
        filters: Словник фільтрів:
            - subject_id: ID предмету
            - date_from: Початкова дата
            - date_to: Кінцева дата
            - min_grade: Мінімальна оцінка
            - max_grade: Максимальна оцінка
            - search_query: Пошук по коментарям/темі

    Returns:
        QuerySet з оцінками студента
    """
    if filters is None:
        filters = {}

    # Базовий запит з оптимізацією
    performance = (
        StudentPerformance.objects.filter(student=student, earned_points__isnull=False)
        .select_related(
            "lesson", "lesson__subject", "lesson__teacher", "lesson__evaluation_type"
        )
        .order_by("-lesson__date")
    )

    # Застосування фільтрів
    if filters.get("subject_id"):
        performance = performance.filter(lesson__subject_id=filters["subject_id"])

    if filters.get("date_from"):
        performance = performance.filter(lesson__date__gte=filters["date_from"])

    if filters.get("date_to"):
        performance = performance.filter(lesson__date__lte=filters["date_to"])

    if filters.get("min_grade"):
        performance = performance.filter(earned_points__gte=filters["min_grade"])

    if filters.get("max_grade"):
        performance = performance.filter(earned_points__lte=filters["max_grade"])

    if filters.get("search_query"):
        query = filters["search_query"]
        performance = performance.filter(
            Q(comment__icontains=query) | Q(lesson__topic__icontains=query)
        )

    return performance


def get_teacher_journal_data(
    teacher: User, subject: Subject, group: StudyGroup, week_shift: int = 0
) -> dict:
    """
    Отримання даних для журналу викладача.

    Args:
        teacher: Викладач
        subject: Предмет
        group: Група
        week_shift: Зсув тижня відносно поточного (0 = цей тиждень)

    Returns:
        Словник з ключами:
            - students: список студентів групи
            - lessons: список уроків за тиждень
            - journal_data: матриця {student_id: {lesson_date: performance}}
            - week_start: дата початку тижня
            - week_end: дата кінця тижня
    """
    # Розрахунок дат тижня
    today = date.today()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    start_of_week = monday + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)

    # Студенти групи
    students = User.objects.filter(role="student", group=group).order_by("full_name")

    # Уроки за тиждень
    lessons = (
        Lesson.objects.filter(
            group=group,
            subject=subject,
            teacher=teacher,
            date__gte=start_of_week,
            date__lte=end_of_week,
        )
        .select_related("evaluation_type")
        .order_by("date", "start_time")
    )

    # Отримання всіх оцінок за тиждень
    performances = StudentPerformance.objects.filter(lesson__in=lessons).select_related(
        "student", "lesson", "absence"
    )

    # Створення матриці журналу
    journal_data = {}
    for student in students:
        journal_data[student.id] = {}
        for lesson in lessons:
            # Ключ: дата + номер уроку (для унікальності)
            key = f"{lesson.date}_{lesson.id}"
            journal_data[student.id][key] = None

    # Заповнення матриці оцінками
    for perf in performances:
        key = f"{perf.lesson.date}_{perf.lesson.id}"
        journal_data[perf.student.id][key] = perf

    return {
        "students": students,
        "lessons": lessons,
        "journal_data": journal_data,
        "week_start": start_of_week,
        "week_end": end_of_week,
    }


def get_schedule_for_group(group: StudyGroup, week_start: date) -> list[Lesson]:
    """
    Отримання розкладу групи на тиждень.

    Args:
        group: Група
        week_start: Дата початку тижня (понеділок)

    Returns:
        Список уроків на тиждень, відсортований по даті та часу
    """
    week_end = week_start + timedelta(days=6)

    lessons = (
        Lesson.objects.filter(group=group, date__gte=week_start, date__lte=week_end)
        .select_related("subject", "teacher", "classroom", "evaluation_type")
        .order_by("date", "start_time")
    )

    return list(lessons)


def get_teacher_assignments(teacher: User) -> QuerySet[TeachingAssignment]:
    """
    Отримання всіх навчальних призначень викладача.

    Args:
        teacher: Викладач

    Returns:
        QuerySet з призначеннями
    """
    return (
        TeachingAssignment.objects.filter(teacher=teacher)
        .select_related("subject", "group")
        .prefetch_related("evaluation_types")
        .order_by("group__name", "subject__name")
    )


def get_subjects_for_group(group: StudyGroup) -> QuerySet[Subject]:
    """
    Отримання всіх предметів, які читаються для групи.

    Args:
        group: Група

    Returns:
        QuerySet з предметами
    """
    return (
        Subject.objects.filter(teachingassignment__group=group)
        .distinct()
        .order_by("name")
    )


def get_group_statistics(group: StudyGroup, subject: Optional[Subject] = None) -> dict:
    """
    Статистика групи по успішності.

    Args:
        group: Група
        subject: Предмет (опціонально, для фільтрації)

    Returns:
        Словник зі статистикою:
            - avg_grade: середня оцінка групи
            - students_count: кількість студентів
            - lessons_count: кількість уроків
            - total_absences: загальна кількість пропусків
    """
    students = User.objects.filter(role="student", group=group)

    # Фільтр по предмету
    performance_filter = Q(student__group=group)
    if subject:
        performance_filter &= Q(lesson__subject=subject)

    # Оцінки
    grades_stats = StudentPerformance.objects.filter(
        performance_filter, earned_points__isnull=False
    ).aggregate(avg=Avg("earned_points"), count=Count("id"))

    # Пропуски
    absences_count = StudentPerformance.objects.filter(
        performance_filter, absence__isnull=False
    ).count()

    # Уроки
    lessons_filter = Q(group=group)
    if subject:
        lessons_filter &= Q(subject=subject)

    lessons_count = Lesson.objects.filter(lessons_filter).count()

    return {
        "avg_grade": float(grades_stats["avg"] or 0),
        "students_count": students.count(),
        "lessons_count": lessons_count,
        "total_absences": absences_count,
    }
