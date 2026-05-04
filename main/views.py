import csv
import json
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Max, Min, Prefetch, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    ClassroomForm,
    ProfileForm,
    StudyGroupForm,
    SubjectForm,
    UserAdminForm,
)
from .models import (
    AbsenceReason,
    BuildingAccessLog,
    Classroom,
    Comment,
    EvaluationType,
    GradeRule,
    GradingScale,
    InstitutionSettings,
    Lesson,
    Notification,
    Post,
    ScheduleTemplate,
    Specialty,
    StudentPerformance,
    StudyGroup,
    Subject,
    TeachingAssignment,
    TimeSlot,
    User,
)

# =========================
# UTILITY & DECORATORS
# =========================


def role_required(allowed_roles: Union[str, List[str]]) -> Callable:
    """
    Декоратор для перевірки ролі через стандартний request.user.
    allowed_roles може бути строкою ('admin') або списком (['admin', 'teacher']).
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func: Callable) -> Callable:
        def wrapper(
            request: HttpRequest, *args: Any, **kwargs: Any
        ) -> Union[HttpResponse, JsonResponse]:
            # 1. Перевірка авторизації Django
            if not request.user.is_authenticated:
                return redirect("login")

            # 2. Перевірка ролі
            if request.user.role not in allowed_roles:
                messages.error(
                    request, "У вас немає прав для доступу до цієї сторінки."
                )
                # Редірект на "свою" сторінку, щоб уникнути циклів
                if request.user.role == "student":
                    return redirect("student_dashboard")
                elif request.user.role == "teacher":
                    return redirect("teacher_dashboard")
                else:
                    return redirect("login")

            # Виконуємо в'юху
            response = view_func(request, *args, **kwargs)

            # Заголовки проти кешування (безпека після логауту)
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

            return response

        return wrapper

    return decorator


def generate_csv_response(filename, header, rows):
    """Утиліта для генерації CSV."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    response.write("\ufeff".encode("utf8"))  # BOM для Excel

    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return response


# =========================
# 1. АУТЕНТИФІКАЦІЯ
# =========================


def login_view(request: HttpRequest) -> HttpResponse:
    """Сторінка входу."""
    if request.user.is_authenticated:
        role = request.user.role
        if role == "admin":
            return redirect("admin_panel")
        if role == "teacher":
            return redirect("teacher_dashboard")
        if role == "student":
            return redirect("student_dashboard")

    response = render(request, "index.html")
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@require_POST
def login_process(request):
    """Обробка входу через стандартний authenticate."""
    email = request.POST.get("username")
    password = request.POST.get("password")

    # Django authenticate хешує пароль і звіряє з БД
    # Важливо: переконайтесь, що в моделі User поле USERNAME_FIELD = 'email'
    user = authenticate(request, email=email, password=password)

    if user is not None:
        login(request, user)  # Створює сесію Django

        if user.role == "admin":
            return redirect("admin_panel")
        elif user.role == "teacher":
            return redirect("teacher_dashboard")
        elif user.role == "student":
            return redirect("student_dashboard")
        else:
            return redirect("login")
    else:
        messages.error(request, "Невірний email або пароль")
        return redirect("login")


def logout_view(request: HttpRequest) -> HttpResponse:
    """Вихід із системи."""
    logout(request)
    response = redirect("login")
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def csrf_debug_view(request: HttpRequest) -> JsonResponse:
    """Debug endpoint: returns the current CSRF token and request cookies.

    Use this temporarily to verify that the CSRF token is generated and that
    the browser is sending cookies correctly.
    """
    try:
        from django.middleware.csrf import get_token
    except Exception:
        return JsonResponse({"error": "csrf module not available"}, status=500)

    token = get_token(request)
    return JsonResponse(
        {
            "csrf_token": token,
            "cookies": request.COOKIES,
            "method": request.method,
        }
    )


# =========================
# 2. АДМІНІСТРАТОР
# =========================


@role_required("admin")
def admin_panel_view(request: HttpRequest) -> HttpResponse:
    course_ctx = request.session.get("global_course")
    specialty_ctx = request.session.get("global_specialty_id")

    users_qs = User.objects.all()
    students_qs = User.objects.filter(role="student")
    groups_qs = StudyGroup.objects.all()

    if course_ctx:
        students_qs = students_qs.filter(group__course=course_ctx)
        groups_qs = groups_qs.filter(course=course_ctx)
    if specialty_ctx:
        students_qs = students_qs.filter(group__specialty_id=specialty_ctx)
        groups_qs = groups_qs.filter(specialty_id=specialty_ctx)

    context = {
        "total_users": users_qs.count(),
        "student_count": students_qs.count(),
        "group_count": groups_qs.count(),
        "subject_count": Subject.objects.count(),
        "classroom_count": Classroom.objects.count(),
        "active_page": "admin",
    }
    return render(request, "admin.html", context)


@role_required("admin")
def institution_settings_view(request: HttpRequest) -> HttpResponse:
    obj = InstitutionSettings.get_instance()
    if obj is None:
        obj = InstitutionSettings()

    if request.method == "POST":
        obj.name = request.POST.get("name", obj.name).strip() or obj.name
        obj.tagline = request.POST.get("tagline", "").strip()
        if "logo" in request.FILES:
            obj.logo = request.FILES["logo"]
        elif request.POST.get("logo_clear"):
            obj.logo = None
        if "favicon" in request.FILES:
            obj.favicon = request.FILES["favicon"]
        elif request.POST.get("favicon_clear"):
            obj.favicon = None
        obj.save()
        messages.success(request, "Налаштування закладу збережено")
        return redirect("institution_settings")

    return render(
        request, "institution_settings.html", {"obj": obj, "active_page": "institution"}
    )


# --- USERS ---
@role_required("admin")
def users_list_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST" and request.user.role != "admin":
        messages.error(request, "Немає прав для додавання користувачів.")
        return redirect("users_list")
    if request.method == "POST":
        form = UserAdminForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Користувача успішно додано")
            return redirect("users_list")
        else:
            messages.error(request, "Помилка при додаванні: " + str(form.errors))
    else:
        form = UserAdminForm()

    # 1. Параметри фільтрації
    role_filter = request.GET.get("role", "")
    group_filter = request.GET.get("group", "")
    subject_filter = request.GET.get("subject", "")
    search_query = request.GET.get("search", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    # 2. Базовий запит
    users = (
        User.objects.select_related("group")
        .prefetch_related("teachingassignment_set__subject")
        .order_by("-id")
    )

    # 3. Фільтри
    if role_filter:
        users = users.filter(role=role_filter)

    if group_filter:
        users = users.filter(group_id=group_filter)

    # Global context filters (apply to students)
    course_ctx = request.session.get("global_course")
    specialty_ctx = request.session.get("global_specialty_id")

    if course_ctx:
        users = users.filter(
            Q(role="student", group__course=course_ctx) | ~Q(role="student")
        )
    if specialty_ctx:
        users = users.filter(
            Q(role="student", group__specialty_id=specialty_ctx) | ~Q(role="student")
        )

    if subject_filter:
        users = users.filter(teachingassignment__subject_id=subject_filter).distinct()

    if search_query:
        users = users.filter(
            Q(full_name__icontains=search_query) | Q(email__icontains=search_query)
        )

    if date_from:
        users = users.filter(created_at__date__gte=date_from)
    if date_to:
        users = users.filter(created_at__date__lte=date_to)

    groups = StudyGroup.objects.all()
    all_subjects = Subject.objects.all()

    paginator = Paginator(users, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "users.html",
        {
            "users": page_obj,
            "page_obj": page_obj,
            "form": form,
            "groups": groups,
            "all_subjects": all_subjects,
            "active_page": "users",
        },
    )


@role_required("admin")
def user_edit_view(request: HttpRequest, pk: int) -> HttpResponse:
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UserAdminForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Дані оновлено")
            return redirect("users_list")
    else:
        form = UserAdminForm(instance=user)

    groups = StudyGroup.objects.all()

    # Отримуємо предмети для цього користувача (якщо це викладач)
    user_subjects = []
    if user.role == "teacher":
        subjects = Subject.objects.filter(teachingassignment__teacher=user).distinct()
        user_subjects = list(subjects)

    return render(
        request,
        "user_edit.html",
        {
            "form": form,
            "user": user,
            "groups": groups,
            "user_subjects": user_subjects,
        },
    )


@role_required(["admin", "teacher"])
def student_detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Детальна сторінка користувача для адміна/викладача."""
    from main.services.grading_service import (
        calculate_weighted_final_grade,
        get_student_absences_stats,
    )

    target_user = get_object_or_404(User, pk=pk)

    subjects_data = []
    if target_user.role == "student" and target_user.group:
        assignments = (
            TeachingAssignment.objects.filter(group=target_user.group, is_active=True)
            .select_related("subject", "teacher")
            .prefetch_related("evaluation_types")
            .order_by("subject__name")
        )
        for assignment in assignments:
            grade_data = calculate_weighted_final_grade(target_user, assignment)
            absence_stats = get_student_absences_stats(target_user, assignment.subject)
            avg_grade = (
                StudentPerformance.objects.filter(
                    student=target_user,
                    lesson__subject=assignment.subject,
                    earned_points__isnull=False,
                ).aggregate(avg=Avg("earned_points"))["avg"]
                or 0
            )
            grades_count = StudentPerformance.objects.filter(
                student=target_user,
                lesson__subject=assignment.subject,
                earned_points__isnull=False,
            ).count()
            subjects_data.append(
                {
                    "subject": assignment.subject,
                    "teacher": assignment.teacher,
                    "semester": assignment.semester,
                    "final_grade": grade_data["final_grade"],
                    "total_weight": grade_data["total_weight"],
                    "contributions": grade_data["contributions"],
                    "absences": absence_stats,
                    "grades_count": grades_count,
                    "avg_grade": round(float(avg_grade), 1),
                }
            )

    teacher_assignments = []
    if target_user.role == "teacher":
        teacher_assignments = list(
            TeachingAssignment.objects.filter(teacher=target_user, is_active=True)
            .select_related("subject", "group")
            .order_by("subject__name", "group__name")
        )

    recent_perf = (
        StudentPerformance.objects.filter(student=target_user)
        .select_related("lesson__subject", "lesson__teacher", "absence")
        .order_by("-lesson__date", "-lesson__start_time")[:20]
    )

    overall = StudentPerformance.objects.filter(
        student=target_user, earned_points__isnull=False
    ).aggregate(avg=Avg("earned_points"), count=Count("id"))

    total_records = StudentPerformance.objects.filter(student=target_user).count()
    total_absences = StudentPerformance.objects.filter(
        student=target_user, absence__isnull=False
    ).count()
    attendance_percent = (
        round((total_records - total_absences) / total_records * 100, 1)
        if total_records > 0
        else 0
    )

    return render(
        request,
        "student_detail.html",
        {
            "target_user": target_user,
            "subjects_data": subjects_data,
            "teacher_assignments": teacher_assignments,
            "recent_perf": recent_perf,
            "avg_grade": round(float(overall["avg"] or 0), 1),
            "grades_count": overall["count"] or 0,
            "attendance_percent": attendance_percent,
            "total_absences": total_absences,
        },
    )


@role_required("admin")
@require_POST
def user_delete_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    # Перевірка через request.user
    if user.id == request.user.id:
        messages.error(request, "Не можна видалити самого себе!")
    else:
        user.delete()
        messages.success(request, "Користувача видалено")
    return redirect("users_list")


@role_required("admin")
def users_csv_export(request):
    """Експортує всіх користувачів у CSV файл."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="users_export.csv"'
    response.write("\ufeff")  # BOM для коректного відкриття у Excel

    writer = csv.writer(response)
    writer.writerow(
        [
            "full_name",
            "email",
            "role",
            "group",
            "phone",
            "date_of_birth",
            "address",
            "student_id",
            "is_active",
        ]
    )

    users = User.objects.select_related("group").all()
    for u in users:
        writer.writerow(
            [
                u.full_name,
                u.email,
                u.role,
                u.group.name if u.group else "",
                u.phone or "",
                u.date_of_birth.strftime("%Y-%m-%d") if u.date_of_birth else "",
                u.address or "",
                u.student_id or "",
                "1" if u.is_active else "0",
            ]
        )
    return response


@role_required("admin")
@require_POST
def users_csv_import(request):
    """Імпортує користувачів з CSV файлу. Обов'язкові поля: full_name, email, role."""
    csv_file = request.FILES.get("csv_file")
    if not csv_file:
        messages.error(request, "Файл не вибрано.")
        return redirect("users_list")

    if not csv_file.name.endswith(".csv"):
        messages.error(request, "Завантажте файл у форматі .csv")
        return redirect("users_list")

    try:
        decoded = csv_file.read().decode("utf-8-sig")  # utf-8-sig знімає BOM
    except UnicodeDecodeError:
        try:
            csv_file.seek(0)
            decoded = csv_file.read().decode("cp1251")
        except UnicodeDecodeError:
            messages.error(
                request, "Не вдалося прочитати файл. Збережіть його в кодуванні UTF-8."
            )
            return redirect("users_list")

    reader = csv.DictReader(decoded.splitlines())

    REQUIRED_FIELDS = {"full_name", "email", "role"}
    VALID_ROLES = {"admin", "teacher", "student"}

    if not reader.fieldnames or not REQUIRED_FIELDS.issubset(set(reader.fieldnames)):
        missing = REQUIRED_FIELDS - set(reader.fieldnames or [])
        messages.error(
            request, f"У CSV відсутні обов'язкові колонки: {', '.join(missing)}"
        )
        return redirect("users_list")

    created_count = 0
    skipped_rows = []

    with transaction.atomic():
        for line_num, row in enumerate(reader, start=2):
            full_name = row.get("full_name", "").strip()
            email = row.get("email", "").strip()
            role = row.get("role", "").strip().lower()

            # Валідація обов'язкових полів
            if not full_name or not email or not role:
                skipped_rows.append(f"Рядок {line_num}: порожні обов'язкові поля")
                continue

            if role not in VALID_ROLES:
                skipped_rows.append(
                    f"Рядок {line_num} ({email}): невалідна роль '{role}'"
                )
                continue

            if User.objects.filter(email=email).exists():
                skipped_rows.append(f"Рядок {line_num} ({email}): email вже існує")
                continue

            # Необов'язкові поля
            password = row.get("password", "").strip() or "ChangeMe123!"
            group = None
            group_name = row.get("group", "").strip()
            if group_name:
                group = StudyGroup.objects.filter(name=group_name).first()

            phone = row.get("phone", "").strip() or None
            address = row.get("address", "").strip() or None
            student_id = row.get("student_id", "").strip() or None
            is_active_raw = row.get("is_active", "1").strip()
            is_active = is_active_raw not in ("0", "false", "False", "ні", "no")

            dob_raw = row.get("date_of_birth", "").strip()
            date_of_birth = None
            if dob_raw:
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                    try:
                        date_of_birth = datetime.strptime(dob_raw, fmt).date()
                        break
                    except ValueError:
                        continue

            User.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
                role=role,
                group=group,
                phone=phone,
                address=address,
                student_id=student_id,
                is_active=is_active,
                date_of_birth=date_of_birth,
            )
            created_count += 1

    if created_count:
        messages.success(request, f"Імпортовано {created_count} користувач(ів).")
    if skipped_rows:
        messages.warning(
            request,
            "Пропущено рядки: "
            + "; ".join(skipped_rows[:10])
            + (
                f" ... та ще {len(skipped_rows) - 10}" if len(skipped_rows) > 10 else ""
            ),
        )
    if not created_count and not skipped_rows:
        messages.info(request, "CSV файл порожній або не містить даних.")

    return redirect("users_list")


# --- GROUPS CSV ---
@role_required("admin")
def groups_csv_export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="groups_export.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        ["name", "specialty", "course", "year_of_entry", "graduation_year", "is_active"]
    )
    for g in StudyGroup.objects.select_related("specialty").all().order_by("name"):
        writer.writerow(
            [
                g.name,
                g.specialty.name if g.specialty else "",
                g.course or "",
                g.year_of_entry or "",
                g.graduation_year or "",
                "1" if g.is_active else "0",
            ]
        )
    return response


@role_required("admin")
@require_POST
def groups_csv_import(request):
    csv_file = request.FILES.get("csv_file")
    if not csv_file or not csv_file.name.endswith(".csv"):
        messages.error(request, "Завантажте файл у форматі .csv")
        return redirect("groups_list")
    try:
        decoded = csv_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = csv_file.read().decode("cp1251")

    reader = csv.DictReader(decoded.splitlines())
    if not reader.fieldnames or "name" not in reader.fieldnames:
        messages.error(request, "У CSV відсутня обов'язкова колонка: name")
        return redirect("groups_list")

    created, skipped = 0, []
    with transaction.atomic():
        for i, row in enumerate(reader, 2):
            name = row.get("name", "").strip()
            if not name:
                skipped.append(f"Рядок {i}: порожня назва")
                continue
            if StudyGroup.objects.filter(name=name).exists():
                skipped.append(f"Рядок {i}: '{name}' вже існує")
                continue
            spec_name = row.get("specialty", "").strip()
            specialty = None
            if spec_name:
                specialty, _ = Specialty.objects.get_or_create(name=spec_name)

            course_raw = row.get("course", "").strip()
            year_entry_raw = row.get("year_of_entry", "").strip()
            grad_year_raw = row.get("graduation_year", "").strip()
            is_active_raw = row.get("is_active", "1").strip()
            StudyGroup.objects.create(
                name=name,
                specialty=specialty,
                course=int(course_raw) if course_raw.isdigit() else None,
                year_of_entry=int(year_entry_raw) if year_entry_raw.isdigit() else None,
                graduation_year=int(grad_year_raw) if grad_year_raw.isdigit() else None,
                is_active=is_active_raw not in ("0", "false", "False", "ні", "no"),
            )
            created += 1

    if created:
        messages.success(request, f"Імпортовано {created} груп(и).")
    if skipped:
        messages.warning(request, "Пропущено: " + "; ".join(skipped[:10]))
    return redirect("groups_list")


# --- SUBJECTS CSV ---
@role_required("admin")
def subjects_csv_export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="subjects_export.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        [
            "name",
            "code",
            "description",
            "credits",
            "hours_total",
            "hours_lectures",
            "hours_practicals",
            "semester",
            "is_active",
        ]
    )
    for s in Subject.objects.all().order_by("name"):
        writer.writerow(
            [
                s.name,
                s.code or "",
                s.description or "",
                s.credits or "",
                s.hours_total or "",
                s.hours_lectures or "",
                s.hours_practicals or "",
                s.semester or "",
                "1" if s.is_active else "0",
            ]
        )
    return response


@role_required("admin")
@require_POST
def subjects_csv_import(request):
    csv_file = request.FILES.get("csv_file")
    if not csv_file or not csv_file.name.endswith(".csv"):
        messages.error(request, "Завантажте файл у форматі .csv")
        return redirect("subjects_list")
    try:
        decoded = csv_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = csv_file.read().decode("cp1251")

    reader = csv.DictReader(decoded.splitlines())
    if not reader.fieldnames or "name" not in reader.fieldnames:
        messages.error(request, "У CSV відсутня обов'язкова колонка: name")
        return redirect("subjects_list")

    created, skipped = 0, []
    with transaction.atomic():
        for i, row in enumerate(reader, 2):
            name = row.get("name", "").strip()
            if not name:
                skipped.append(f"Рядок {i}: порожня назва")
                continue
            if Subject.objects.filter(name=name).exists():
                skipped.append(f"Рядок {i}: '{name}' вже існує")
                continue

            def _int(val):
                return int(val) if str(val).strip().isdigit() else None

            Subject.objects.create(
                name=name,
                code=row.get("code", "").strip(),
                description=row.get("description", "").strip(),
                credits=_int(row.get("credits", "")),
                hours_total=_int(row.get("hours_total", "")),
                hours_lectures=_int(row.get("hours_lectures", "")),
                hours_practicals=_int(row.get("hours_practicals", "")),
                semester=_int(row.get("semester", "")),
                is_active=row.get("is_active", "1").strip()
                not in ("0", "false", "False", "ні", "no"),
            )
            created += 1

    if created:
        messages.success(request, f"Імпортовано {created} предмет(ів).")
    if skipped:
        messages.warning(request, "Пропущено: " + "; ".join(skipped[:10]))
    return redirect("subjects_list")


# --- CLASSROOMS CSV ---
@role_required("admin")
def classrooms_csv_export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="classrooms_export.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        ["name", "building", "floor", "capacity", "type", "equipment", "is_active"]
    )
    for c in Classroom.objects.all().order_by("name"):
        writer.writerow(
            [
                c.name,
                c.building or "",
                c.floor or "",
                c.capacity or "",
                c.type or "",
                c.equipment or "",
                "1" if c.is_active else "0",
            ]
        )
    return response


@role_required("admin")
@require_POST
def classrooms_csv_import(request):
    csv_file = request.FILES.get("csv_file")
    if not csv_file or not csv_file.name.endswith(".csv"):
        messages.error(request, "Завантажте файл у форматі .csv")
        return redirect("classrooms_list")
    try:
        decoded = csv_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = csv_file.read().decode("cp1251")

    reader = csv.DictReader(decoded.splitlines())
    if not reader.fieldnames or "name" not in reader.fieldnames:
        messages.error(request, "У CSV відсутня обов'язкова колонка: name")
        return redirect("classrooms_list")

    VALID_TYPES = {"lecture", "computer", "lab", "other", ""}
    created, skipped = 0, []
    with transaction.atomic():
        for i, row in enumerate(reader, 2):
            name = row.get("name", "").strip()
            if not name:
                skipped.append(f"Рядок {i}: порожня назва")
                continue
            if Classroom.objects.filter(name=name).exists():
                skipped.append(f"Рядок {i}: '{name}' вже існує")
                continue

            def _int(val):
                return int(val) if str(val).strip().isdigit() else None

            room_type = row.get("type", "other").strip()
            if room_type not in VALID_TYPES:
                room_type = "other"
            Classroom.objects.create(
                name=name,
                building=row.get("building", "").strip(),
                floor=_int(row.get("floor", "")),
                capacity=_int(row.get("capacity", "")),
                type=room_type or "other",
                equipment=row.get("equipment", "").strip(),
                is_active=row.get("is_active", "1").strip()
                not in ("0", "false", "False", "ні", "no"),
            )
            created += 1

    if created:
        messages.success(request, f"Імпортовано {created} аудиторій.")
    if skipped:
        messages.warning(request, "Пропущено: " + "; ".join(skipped[:10]))
    return redirect("classrooms_list")


# --- GROUPS ---
@role_required("admin")
def groups_list_view(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        specialty_id = request.POST.get("specialty_id")
        course = request.POST.get("course")
        year_of_entry = request.POST.get("year_of_entry")
        graduation_year = request.POST.get("graduation_year")
        if name:
            specialty = None
            if specialty_id and specialty_id.isdigit():
                specialty = Specialty.objects.filter(pk=int(specialty_id)).first()
            StudyGroup.objects.create(
                name=name,
                specialty=specialty,
                course=int(course) if course and course.isdigit() else None,
                year_of_entry=(
                    int(year_of_entry)
                    if year_of_entry and year_of_entry.isdigit()
                    else None
                ),
                graduation_year=(
                    int(graduation_year)
                    if graduation_year and graduation_year.isdigit()
                    else None
                ),
            )
            messages.success(request, f"Групу '{name}' додано")
        else:
            messages.error(request, "Назва групи є обов'язковою")
        return redirect("groups_list")

    search_query = request.GET.get("search", "")

    # GET filters take priority, session context is fallback
    course_filter = request.GET.get("course") or request.session.get("global_course")
    specialty_filter = request.GET.get("specialty") or request.session.get(
        "global_specialty_id"
    )

    groups = (
        StudyGroup.objects.select_related("specialty")
        .prefetch_related("students")
        .annotate(student_count=Count("students"))
        .order_by("name")
    )

    if search_query:
        groups = groups.filter(
            Q(name__icontains=search_query) | Q(specialty__name__icontains=search_query)
        )
    if course_filter and str(course_filter).isdigit():
        groups = groups.filter(course=int(course_filter))
    if specialty_filter and str(specialty_filter).isdigit():
        groups = groups.filter(specialty_id=int(specialty_filter))

    specialties = Specialty.objects.all().order_by("code", "name")

    return render(
        request,
        "groups.html",
        {
            "groups": groups,
            "form": StudyGroupForm(),
            "specialties": specialties,
            "active_page": "groups",
        },
    )


@role_required("admin")
@require_POST
def group_add_view(request):
    form = StudyGroupForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Групу додано")
    else:
        messages.error(request, "Помилка: така група вже існує")
    return redirect("groups_list")


@role_required("admin")
@require_POST
def group_delete_view(request, pk):
    group = get_object_or_404(StudyGroup, pk=pk)
    group.delete()
    messages.success(request, "Групу видалено")
    return redirect("groups_list")


# =========================
# GLOBAL CONTEXT SWITCHER
# =========================


@login_required
@require_POST
def set_global_context_view(request):
    """Saves the selected course/specialty into the user session."""
    course_raw = request.POST.get("course", "").strip()
    specialty_id_raw = request.POST.get("specialty_id", "").strip()

    if course_raw and course_raw.isdigit() and 1 <= int(course_raw) <= 6:
        request.session["global_course"] = int(course_raw)
    else:
        request.session["global_course"] = None

    if specialty_id_raw and specialty_id_raw.isdigit():
        request.session["global_specialty_id"] = int(specialty_id_raw)
    else:
        request.session["global_specialty_id"] = None

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    return redirect(next_url)


# =========================
# SPECIALTIES CRUD
# =========================


@role_required("admin")
def specialties_list_view(request):
    """Manage specialties (Спеціальності)."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        description = request.POST.get("description", "").strip()
        if name:
            _, created = Specialty.objects.get_or_create(
                name=name,
                defaults={"code": code, "description": description},
            )
            if created:
                messages.success(request, f"Спеціальність '«{name}»' додано")
            else:
                messages.warning(request, "Така спеціальність вже існує")
        else:
            messages.error(request, "Назва спеціальності є обов'язковою")
        return redirect("specialties_list")

    search_query = request.GET.get("search", "").strip()
    specialties = (
        Specialty.objects.prefetch_related("groups")
        .annotate(group_count=Count("groups"))
        .order_by("code", "name")
    )
    if search_query:
        specialties = specialties.filter(
            Q(name__icontains=search_query) | Q(code__icontains=search_query)
        )
    return render(
        request,
        "specialties.html",
        {
            "specialties": specialties,
            "active_page": "specialties",
        },
    )


@role_required("admin")
@require_POST
def specialty_delete_view(request, pk):
    specialty = get_object_or_404(Specialty, pk=pk)
    if specialty.groups.exists():
        messages.error(
            request, "Неможна видалити — з цією спеціальністю пов'язані групи"
        )
    else:
        specialty.delete()
        messages.success(request, "Спеціальність видалено")
    return redirect("specialties_list")


@role_required("admin")
@require_POST
def specialty_edit_view(request, pk):
    specialty = get_object_or_404(Specialty, pk=pk)
    name = request.POST.get("name", "").strip()
    code = request.POST.get("code", "").strip()
    description = request.POST.get("description", "").strip()
    if name:
        specialty.name = name
        specialty.code = code
        specialty.description = description
        specialty.save()
        messages.success(request, "Спеціальність оновлено")
    else:
        messages.error(request, "Назва бов'язкова")
    return redirect("specialties_list")


@role_required("admin")
def subjects_list_view(request):
    search_query = request.GET.get("search", "")
    subjects = Subject.objects.annotate(
        teachers_count=Count("teachingassignment")
    ).order_by("name")

    if search_query:
        subjects = subjects.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    form = SubjectForm()
    return render(
        request,
        "subjects.html",
        {"subjects": subjects, "form": form, "active_page": "subjects"},
    )


@role_required("admin")
def subject_add_view(request):
    if request.method == "POST":
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Предмет додано")
            return redirect("subjects_list")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect("subjects_list")
    else:
        subjects = Subject.objects.annotate(
            teachers_count=Count("teachingassignment")
        ).order_by("name")
        form = SubjectForm()
        return render(request, "subjects.html", {"subjects": subjects, "form": form})


@role_required("admin")
@require_POST
def subject_delete_view(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    try:
        subject.delete()
        messages.success(request, "Предмет видалено")
    except Exception as e:
        messages.error(
            request,
            "Неможливо видалити предмет, він використовується в системі.",
        )
    return redirect("subjects_list")


# --- CLASSROOMS ---
@role_required("admin")
def classrooms_list_view(request):
    search_query = request.GET.get("search", "")
    classrooms = Classroom.objects.all().order_by("name")

    if search_query:
        classrooms = classrooms.filter(
            Q(name__icontains=search_query) | Q(building__icontains=search_query)
        )

    form = ClassroomForm()
    return render(
        request,
        "classrooms.html",
        {"classrooms": classrooms, "form": form, "active_page": "classrooms"},
    )


@role_required("admin")
@require_POST
def classroom_add_view(request):
    form = ClassroomForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Аудиторію додано")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    return redirect("classrooms_list")


@role_required("admin")
@require_POST
def classroom_delete_view(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk)
    try:
        classroom.delete()
        messages.success(request, "Аудиторію видалено")
    except Exception as e:
        messages.error(
            request,
            "Неможливо видалити аудиторію, вона використовується в системі.",
        )
    return redirect("classrooms_list")


# --- SCHEDULE ---
@role_required("admin")
def set_weekly_schedule_view(request):
    """Сторінка налаштування розкладу."""
    if request.method == "POST":
        return save_schedule_changes(request)

    groups = StudyGroup.objects.all().order_by("name")

    assignments = TeachingAssignment.objects.select_related(
        "subject", "teacher", "group"
    ).order_by("group__name", "subject__name")

    subject_teachers = defaultdict(list)
    for assignment in assignments:
        subj_id = assignment.subject.id
        teacher_tuple = (assignment.teacher.id, assignment.teacher.full_name)
        if teacher_tuple not in subject_teachers[subj_id]:
            subject_teachers[subj_id].append(teacher_tuple)

    current_schedule = ScheduleTemplate.objects.all().select_related(
        "subject", "teacher", "group"
    )

    schedule_map_temp = defaultdict(lambda: defaultdict(dict))
    for item in current_schedule:
        grp_id = str(item.group.id)
        day = str(item.day_of_week)

        # Зберегти всі уроки, незалежно від часу
        # Використовувати lesson_number з бази даних (він повинен бути встановлений коректно)
        lesson_num = item.lesson_number
        if lesson_num:
            schedule_map_temp[grp_id][day][str(lesson_num)] = {
                "subject_id": item.subject.id,
                "subject_name": item.subject.name,
                "teacher_id": item.teacher.id,
                "teacher_name": item.teacher.full_name,
                "start_time": item.start_time.strftime("%H:%M"),
                "duration": item.duration_minutes,  # Важливо
                "classroom": item.classroom.name if item.classroom else "",
            }

    schedule_map = {}
    for grp_id, days in schedule_map_temp.items():
        schedule_map[grp_id] = {}
        for day, lessons in days.items():
            schedule_map[grp_id][day] = dict(lessons)

    subjects = Subject.objects.all().order_by("name")
    subject_data = []
    subject_teachers_map = {}

    for subject in subjects:
        teachers = (
            TeachingAssignment.objects.filter(subject=subject)
            .select_related("teacher")
            .values_list("teacher_id", "teacher__full_name")
            .distinct()
        )
        teachers_list = list(teachers)

        if teachers_list:
            subject_teachers_map[subject.id] = [
                {"id": tid, "name": tname} for tid, tname in teachers_list
            ]
            subject_data.append(
                {
                    "id": subject.id,
                    "name": subject.name,
                }
            )

    lesson_times = {
        1: ("08:00", "08:50"),
        2: ("09:00", "09:50"),
        3: ("10:00", "10:50"),
        4: ("12:00", "12:50"),
        5: ("13:00", "13:50"),
        6: ("14:00", "14:50"),
        7: ("15:00", "15:50"),
    }

    context = {
        "groups": groups,
        "schedule_map": schedule_map,
        "subject_data": subject_data,
        "subject_teachers_map": subject_teachers_map,
        "days": [
            (1, "Понеділок"),
            (2, "Вівторок"),
            (3, "Середа"),
            (4, "Четвер"),
            (5, "П'ятниця"),
        ],
        "lesson_numbers": range(1, 8),
        "lesson_times": lesson_times,
        "active_page": "schedule_builder",
    }
    return render(request, "main/schedule_builder.html", context)


@require_POST
@role_required("admin")
def save_schedule_changes(request: HttpRequest) -> JsonResponse:
    """API endpoint для збереження розкладу."""
    try:
        data = json.loads(request.body)
        group_id = data.get("group_id")
        schedule_entries = data.get("schedule", {})

        if not group_id:
            return JsonResponse(
                {"status": "error", "message": "Група не вибрана"}, status=400
            )

        group = get_object_or_404(StudyGroup, id=group_id)

        with transaction.atomic():
            # Імпорт валідаційного сервісу
            from main.services.schedule_service import validate_schedule_slot

            # Крок 1: Підготовка та валідація ВСІХ нових слотів (перед видаленням!)
            # Це дозволяє exclude_slot_id працювати правильно, оскільки старі слоти ще в БД
            slots_to_create = []

            for day_str, lessons in schedule_entries.items():
                day = int(day_str)
                for lesson_num_str, lesson_data in lessons.items():
                    lesson_num = int(lesson_num_str)

                    if isinstance(lesson_data, dict):
                        subject_id = lesson_data.get("subject_id")
                        teacher_id = lesson_data.get("teacher_id")
                    else:
                        subject_id = lesson_data
                        teacher_id = None

                    if subject_id:
                        # Підготовка даних для слоту
                        assignment = None
                        if teacher_id:
                            teacher = User.objects.filter(id=teacher_id).first()
                            if teacher:
                                assignment, _ = (
                                    TeachingAssignment.objects.get_or_create(
                                        group=group,
                                        subject_id=subject_id,
                                        teacher=teacher,
                                    )
                                )

                        if not assignment:
                            assignment = TeachingAssignment.objects.filter(
                                group=group, subject_id=subject_id
                            ).first()

                        start_time_str = "08:30"
                        classroom_name = ""
                        duration = 90
                        if isinstance(lesson_data, dict):
                            start_time_str = lesson_data.get(
                                "startTime", lesson_data.get("start_time", "08:30")
                            )
                            classroom_name = lesson_data.get("classroom", "").strip()
                            duration = int(lesson_data.get("duration", 90))

                        classroom_obj = None
                        if classroom_name:
                            classroom_obj, _ = Classroom.objects.get_or_create(
                                name=classroom_name
                            )

                        import datetime as _dt

                        start_time_obj = _dt.datetime.strptime(
                            start_time_str, "%H:%M"
                        ).time()

                        teacher_obj = None
                        if teacher_id:
                            teacher_obj = User.objects.filter(id=teacher_id).first()
                        elif assignment:
                            teacher_obj = assignment.teacher

                        # Знайти існуючий слот для виключення з перевірки конфліктів
                        existing_slot = ScheduleTemplate.objects.filter(
                            group=group, day_of_week=day, lesson_number=lesson_num
                        ).first()
                        exclude_id = existing_slot.id if existing_slot else None

                        # ВАЛІДАЦІЯ: check_current_group=False ігнорує конфлікти з цією ж групою,
                        # оскільки ми зараз перезаписуємо весь її розклад
                        is_valid, err = validate_schedule_slot(
                            group=group,
                            day=day,
                            lesson_number=lesson_num,
                            start_time=start_time_obj,
                            duration=duration,
                            subject=Subject.objects.filter(id=subject_id).first(),
                            teacher=teacher_obj,
                            classroom=classroom_obj,
                            exclude_slot_id=exclude_id,
                            check_current_group=False,
                        )

                        if not is_valid:
                            day_name = {
                                1: "Пн",
                                2: "Вт",
                                3: "Ср",
                                4: "Чт",
                                5: "Пт",
                                6: "Сб",
                                7: "Нд",
                            }.get(day, str(day))
                            return JsonResponse(
                                {
                                    "status": "error",
                                    "message": f"Конфлікт ({day_name}, пара №{lesson_num}): {err}",
                                },
                                status=400,
                            )

                        # Зберігаємо дані для створення після видалення
                        slots_to_create.append(
                            {
                                "group": group,
                                "subject_id": subject_id,
                                "teacher_id": teacher_id
                                or (assignment.teacher_id if assignment else None),
                                "assignment": assignment,
                                "day_of_week": day,
                                "lesson_number": lesson_num,
                                "start_time": start_time_str,
                                "duration_minutes": duration,
                                "classroom": classroom_obj,
                            }
                        )

            # Крок 2: Видалити ВСІ старі слоти (валідація вже пройдена!)
            ScheduleTemplate.objects.filter(group=group).delete()

            # Крок 3: Створити нові слоти
            for slot_data in slots_to_create:
                ScheduleTemplate.objects.create(
                    group=slot_data["group"],
                    subject_id=slot_data["subject_id"],
                    teacher_id=slot_data["teacher_id"],
                    teaching_assignment=slot_data["assignment"],
                    day_of_week=slot_data["day_of_week"],
                    lesson_number=slot_data["lesson_number"],
                    start_time=slot_data["start_time"],
                    duration_minutes=slot_data["duration_minutes"],
                    classroom=slot_data["classroom"],
                    valid_from=date.today(),
                )

        return JsonResponse(
            {"status": "success", "message": f"Розклад для групи {group.name} оновлено"}
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "Невірний формат JSON"}, status=400
        )
    except Exception:
        logger.exception("save_schedule_changes: unexpected error")
        return JsonResponse(
            {"status": "error", "message": "Внутрішня помилка сервера"}, status=500
        )


@role_required("admin")
def schedule_editor_view(request: HttpRequest) -> HttpResponse:
    """Новий редактор розкладу (List View) з 8 слотами."""
    group_id = request.GET.get("group_id")
    groups = StudyGroup.objects.all().order_by("name")

    selected_group = None
    if group_id:
        selected_group = get_object_or_404(StudyGroup, id=group_id)

    # Структура днів та слотів
    days_info = [
        (1, "ПОНЕДІЛОК"),
        (2, "ВІВТОРОК"),
        (3, "СЕРЕДА"),
        (4, "ЧЕТВЕР"),
        (5, "П'ЯТНИЦЯ"),
    ]

    schedule_data = []  # Список об'єктів для кожного дня

    if selected_group:
        templates = ScheduleTemplate.objects.filter(
            group=selected_group
        ).select_related("subject", "teacher", "classroom")
        template_dict = defaultdict(dict)
        for t in templates:
            template_dict[t.day_of_week][t.lesson_number] = t

        for day_num, day_name in days_info:
            slots = []
            for i in range(1, 8):  # 7 слотів
                template = template_dict[day_num].get(i)
                slots.append(
                    {"number": i, "template": template, "is_empty": template is None}
                )
            schedule_data.append(
                {"day_num": day_num, "day_name": day_name, "slots": slots}
            )

    # Довідкові дані для модального вікна
    subjects = Subject.objects.all().order_by("name")
    teachers = User.objects.filter(role="teacher").order_by("full_name")
    classrooms = Classroom.objects.all().order_by("name")

    context = {
        "groups": groups,
        "selected_group": selected_group,
        "schedule_data": schedule_data,
        "subjects": subjects,
        "teachers": teachers,
        "classrooms": classrooms,
        "active_page": "schedule_editor",
    }
    return render(request, "main/schedule_editor.html", context)


@require_POST
@role_required("admin")
def api_save_schedule_slot(request: HttpRequest) -> JsonResponse:
    """API для збереження окремого слоту в ScheduleTemplate."""
    try:
        # Імпорт сервісу та форми
        from main.forms import ScheduleSlotForm
        from main.services.schedule_service import validate_schedule_slot

        data = json.loads(request.body)

        # Валідація вхідних даних через форму
        form = ScheduleSlotForm(data)
        if not form.is_valid():
            return JsonResponse(
                {
                    "status": "error",
                    "message": f"Помилка даних: {form.errors.as_text()}",
                },
                status=400,
            )

        cd = form.cleaned_data
        group_id = cd["group_id"]
        day = cd["day"]
        lesson_num = cd["lesson_number"]

        subject_id = cd.get("subject_id")
        teacher_id = cd.get("teacher_id")
        classroom_id = cd.get("classroom_id")
        start_time = cd["start_time"]
        duration = cd["duration"]

        group = get_object_or_404(StudyGroup, id=group_id)

        # Видалення якщо вибрано "пусто" (subject_id=None)
        if not subject_id:
            ScheduleTemplate.objects.filter(
                group=group, day_of_week=day, lesson_number=lesson_num
            ).delete()
            return JsonResponse({"status": "success", "message": "Слот очищено"})

        # (Конвертація часу вже зроблена формою)

        # Отримання об'єктів
        subject = get_object_or_404(Subject, id=subject_id)
        teacher = None
        if teacher_id:
            teacher = get_object_or_404(User, id=teacher_id)

        classroom = None
        if classroom_id:
            classroom = get_object_or_404(Classroom, id=classroom_id)

        # Знайти існуючий слот (для виключення при валідації)
        existing_slot = ScheduleTemplate.objects.filter(
            group=group, day_of_week=day, lesson_number=lesson_num
        ).first()
        exclude_id = existing_slot.id if existing_slot else None

        # VALIDATION через сервіс (замість 60+ рядків коду!)
        is_valid, error_message = validate_schedule_slot(
            group=group,
            day=day,
            lesson_number=lesson_num,
            start_time=start_time,
            duration=duration,
            subject=subject,
            teacher=teacher,
            classroom=classroom,
            exclude_slot_id=exclude_id,
        )

        if not is_valid:
            return JsonResponse(
                {"status": "error", "message": f"Конфлікт: {error_message}"}, status=400
            )

        # 1. Знаходимо або створюємо TeachingAssignment (SSOT)
        # У майбутньому це буде обов'язковим, зараз - забезпечуємо міграцію нових даних
        assignment = None
        if teacher:
            assignment, _ = TeachingAssignment.objects.get_or_create(
                subject=subject, teacher=teacher, group=group
            )

        # SAVE - з урахуванням можливості None для teacher
        with transaction.atomic():
            # Якщо викладач не вказаний, але є assignment (наприклад збережений раніше),
            # використаємо його викладача. Інакше залишимо None (модель дозволяє null тепер).
            teacher_to_save = teacher or (assignment.teacher if assignment else None)

            template, created = ScheduleTemplate.objects.update_or_create(
                group=group,
                day_of_week=day,
                lesson_number=lesson_num,
                defaults={
                    "subject": subject,
                    "teacher": teacher_to_save,
                    "teaching_assignment": assignment,  # <-- НОВЕ ПОЛЕ
                    "classroom": classroom,
                    "start_time": start_time,
                    "duration_minutes": duration,
                },
            )

        return JsonResponse(
            {
                "status": "success",
                "message": "Збережено",
                "data": {
                    "subject": template.subject.name,
                    "teacher": template.teacher.full_name if template.teacher else "—",
                    "classroom": template.classroom.name if template.classroom else "—",
                    "time": f'{template.start_time.strftime("%H:%M")} (+{template.duration_minutes}хв)',
                },
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "Невірний JSON формат"}, status=400
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse(
            {"status": "error", "message": f"Помилка при збереженні: {str(e)}"},
            status=500,
        )


@login_required
def schedule_view(request):
    user = request.user

    group_id = request.GET.get("group_id")
    week_shift = int(request.GET.get("week", 0))

    group = None
    if user.role == "student":
        group = user.group
    elif group_id:
        group = get_object_or_404(StudyGroup, id=group_id)

    # Розрахунок дат тижня
    today = date.today()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    start_of_week = monday + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)

    # Замість Lesson використовуємо ScheduleTemplate
    schedule_templates = []
    if group:
        schedule_templates = (
            ScheduleTemplate.objects.filter(group=group)
            .select_related("subject", "teacher", "classroom")
            .order_by("day_of_week", "lesson_number")
        )

    # Дні тижня для заголовка
    week_days = []
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
    for i in range(7):
        d = start_of_week + timedelta(days=i)
        week_days.append(
            {
                "date": d,
                "day_name": day_names[i],
                "day_of_week": i + 1,  # 1=Пн, 2=Вт, ..., 7=Нд
                "is_today": d == today,
            }
        )

    context = {
        "schedule_templates": schedule_templates,  # Замість 'lessons'
        "week_days": week_days,
        "group": group,
        "all_groups": (
            StudyGroup.objects.all().order_by("name")
            if user.role != "student"
            else None
        ),
        "week_shift": week_shift,
        "start_of_week": start_of_week,
        "end_of_week": end_of_week,
        "active_page": "schedule",
    }

    return render(request, "schedule_timelord.html", context)


# =========================
# 3. ВИКЛАДАЧ
# =========================


@role_required("teacher")
def teacher_journal_view(request: HttpRequest) -> HttpResponse:
    from main.services.grading_service import get_teacher_journal_context

    teacher_id = request.user.id

    # Get all assignments for the teacher to populate filters
    assignments = TeachingAssignment.objects.filter(
        teacher_id=teacher_id
    ).select_related("subject", "group")

    selected_subject_id = request.GET.get("subject")
    selected_group_id = request.GET.get("group")

    # Parse week offset
    try:
        week_offset = int(request.GET.get("week", 0))
    except (ValueError, TypeError):
        week_offset = 0

    groups = []
    seen_groups = set()
    for assignment in assignments:
        if assignment.group.id not in seen_groups:
            groups.append({"id": assignment.group.id, "name": assignment.group.name})
            seen_groups.add(assignment.group.id)

    # Filter subjects based on selected group if one is picked
    subjects = []
    seen_subjects = set()
    subject_assignments = assignments
    if selected_group_id:
        subject_assignments = assignments.filter(group_id=selected_group_id)

    for assignment in subject_assignments:
        if assignment.subject.id not in seen_subjects:
            subjects.append(
                {"id": assignment.subject.id, "name": assignment.subject.name}
            )
            seen_subjects.add(assignment.subject.id)

    context = {
        "subjects": sorted(subjects, key=lambda x: x["name"]),
        "groups": sorted(groups, key=lambda x: x["name"]),
        "selected_subject_id": selected_subject_id,
        "selected_group_id": selected_group_id,
        "week_offset": week_offset,
        "active_page": "teacher",
    }

    if selected_subject_id and selected_group_id:
        try:
            # Check if this specific assignment exists for the teacher
            selected_assignment = assignments.filter(
                subject_id=selected_subject_id, group_id=selected_group_id
            ).first()

            if not selected_assignment:
                messages.warning(
                    request, "У вас немає призначення на цей предмет у цій групі."
                )
            else:
                journal_context = get_teacher_journal_context(
                    group_id=int(selected_group_id),
                    subject_id=int(selected_subject_id),
                    week_offset=week_offset,
                )
                context.update(journal_context)
                context["selected_assignment"] = selected_assignment

        except Exception as e:
            messages.error(request, f"Помилка завантаження журналу: {str(e)}")

    return render(request, "teacher.html", context)


@require_POST
def api_save_grade(request: HttpRequest) -> JsonResponse:
    """
    API для миттєвого збереження оцінки.
    Payload: { student_id, date, lesson_num, subject_id, value, comment }
    """
    from main.services.grading_service import save_grade as _save_grade

    if not request.user.is_authenticated or request.user.role != "teacher":
        return JsonResponse({"status": "error", "message": "Forbidden"}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "Невірний формат JSON"}, status=400
        )

    try:
        # Підтримка як плоского, так і вкладеного формату payload
        if "changes" in data and len(data["changes"]) > 0:
            data = data["changes"][0]
            student_id = data.get("student_pk")
        else:
            student_id = data.get("student_id")

        result = _save_grade(
            teacher_id=request.user.id,
            student_id=student_id,
            lesson_id=data.get("lesson_id"),
            lesson_date_str=data.get("date"),
            lesson_num=data.get("lesson_num"),
            subject_id=data.get("subject_id"),
            raw_value=data.get("value"),
            absence_id=data.get("absence_id"),
            has_absence_id="absence_id" in data,
            comment_text=data.get("comment"),
        )
        status_code = 200 if result["status"] == "success" else 400
        return JsonResponse(result, status=status_code)

    except Exception:
        logger.exception("api_save_grade: unexpected error")
        return JsonResponse(
            {"status": "error", "message": "Внутрішня помилка сервера"}, status=500
        )


# =========================
# 4. СТУДЕНТ
# =========================


@role_required("student")
def student_grades_view(request: HttpRequest) -> HttpResponse:
    """Сторінка оцінок студента."""
    from main.selectors import get_student_performance_data, get_subjects_for_group

    student = request.user

    # Збираємо фільтри з request.GET
    filters = {
        "date_from": request.GET.get("date_from"),
        "date_to": request.GET.get("date_to"),
        "subject_id": request.GET.get("subject"),
        "min_grade": request.GET.get("min_grade"),
        "max_grade": request.GET.get("max_grade"),
        "search_query": request.GET.get("search"),
    }

    # Видаляємо None значення
    filters = {k: v for k, v in filters.items() if v}

    # Використовуємо селектор для отримання оцінок
    grades = get_student_performance_data(student, filters)

    # Отримуємо предмети групи
    student_subjects = get_subjects_for_group(student.group)

    return render(
        request,
        "student_grades.html",
        {
            "grades": grades,
            "student_subjects": student_subjects,
            "active_page": "student_grades",
        },
    )


@role_required("student")
def student_attendance_view(request: HttpRequest) -> HttpResponse:
    student = request.user

    search_query = request.GET.get("search", "")
    subject_id = request.GET.get("subject", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    is_respectful = request.GET.get("is_respectful", "")

    absences = StudentPerformance.objects.filter(
        student=student, absence__isnull=False
    ).select_related("lesson__subject", "lesson__teacher", "absence")

    if search_query:
        absences = absences.filter(lesson__topic__icontains=search_query)

    if subject_id:
        absences = absences.filter(lesson__subject_id=subject_id)

    if date_from:
        absences = absences.filter(lesson__date__gte=date_from)

    if date_to:
        absences = absences.filter(lesson__date__lte=date_to)

    if is_respectful == "1":
        absences = absences.filter(absence__is_respectful=True)
    elif is_respectful == "0":
        absences = absences.filter(absence__is_respectful=False)

    absences = absences.order_by("-lesson__date")

    total_absences = absences.count()
    unexcused = absences.filter(absence__is_respectful=False).count()

    student_subjects = Subject.objects.filter(
        teachingassignment__group=student.group
    ).distinct()

    context = {
        "absences": absences,
        "total": total_absences,
        "unexcused": unexcused,
        "student_subjects": student_subjects,
        "active_page": "student_attendance",
    }
    return render(request, "student_attendance.html", context)


@role_required("student")
def student_semester_grades_view(request: HttpRequest) -> HttpResponse:
    """Семестрові оцінки студента по кожному предмету (зважені)."""
    from main.services.grading_service import calculate_weighted_final_grade

    student = request.user

    assignments = (
        TeachingAssignment.objects.filter(group=student.group, is_active=True)
        .select_related("subject", "teacher")
        .prefetch_related("evaluation_types")
        .order_by("subject__name")
    )

    semester_data = []
    for assignment in assignments:
        grade_data = calculate_weighted_final_grade(student, assignment)
        total_lessons = StudentPerformance.objects.filter(
            student=student, lesson__subject=assignment.subject
        ).count()
        total_absences = StudentPerformance.objects.filter(
            student=student,
            lesson__subject=assignment.subject,
            absence__isnull=False,
        ).count()
        semester_data.append(
            {
                "subject": assignment.subject,
                "teacher": assignment.teacher,
                "semester": assignment.semester,
                "academic_year": assignment.academic_year,
                "final_grade": grade_data["final_grade"],
                "total_weight": grade_data["total_weight"],
                "contributions": grade_data["contributions"],
                "total_lessons": total_lessons,
                "total_absences": total_absences,
            }
        )

    return render(
        request,
        "student_semester.html",
        {
            "semester_data": semester_data,
            "active_page": "student_semester",
        },
    )


@role_required("teacher")
def teacher_dashboard_view(request):
    """
    Командний центр викладача.
    Показує: розклад на сьогодні, проблемних студентів, статистику.
    """
    import json
    from datetime import datetime
    from datetime import time as dtime

    teacher = request.user
    today = date.today()
    now = datetime.now().time()

    course_ctx = request.session.get("global_course")
    specialty_ctx = request.session.get("global_specialty_id")

    # 1. Розклад на СЬОГОДНІ
    today_lessons_qs = Lesson.objects.filter(teacher=teacher, date=today)
    if course_ctx:
        today_lessons_qs = today_lessons_qs.filter(group__course=course_ctx)
    if specialty_ctx:
        today_lessons_qs = today_lessons_qs.filter(group__specialty_id=specialty_ctx)

    today_lessons = list(
        today_lessons_qs.select_related(
            "group", "subject", "classroom", "evaluation_type"
        ).order_by("start_time")
    )

    # Поточна або наступна пара
    current_lesson = None
    next_lesson = None
    for lesson in today_lessons:
        if lesson.start_time <= now <= lesson.end_time:
            current_lesson = lesson
            break
        elif lesson.start_time > now and next_lesson is None:
            next_lesson = lesson

    # 2. "Радар Ризику"
    my_groups_qs = TeachingAssignment.objects.filter(teacher=teacher)
    if course_ctx:
        my_groups_qs = my_groups_qs.filter(group__course=course_ctx)
    if specialty_ctx:
        my_groups_qs = my_groups_qs.filter(group__specialty_id=specialty_ctx)

    my_groups = my_groups_qs.values_list("group", flat=True)

    risk_students = []
    students_in_danger = (
        User.objects.filter(group__in=my_groups, role="student")
        .annotate(
            absences_count=Count(
                "studentperformance",
                filter=Q(studentperformance__absence__isnull=False),
            )
        )
        .filter(absences_count__gte=3)
        .order_by("-absences_count")[:5]
    )

    for s in students_in_danger:
        risk_students.append(
            {
                "name": s.full_name,
                "group": s.group.name,
                "issue": f"{s.absences_count} пропусків",
                "severity": "high" if s.absences_count > 5 else "medium",
            }
        )

    # 3. Навантаження по днях тижня (для графіку)
    start_week = today - timedelta(days=today.weekday())
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
    weekly_by_day = []
    for i in range(7):
        day = start_week + timedelta(days=i)
        count = Lesson.objects.filter(teacher=teacher, date=day).count()
        weekly_by_day.append(count)

    weekly_load = sum(weekly_by_day)

    context = {
        "today_lessons": today_lessons,
        "current_lesson": current_lesson,
        "next_lesson": next_lesson,
        "risk_students": risk_students,
        "weekly_load": weekly_load,
        "weekly_labels_json": json.dumps(day_names),
        "weekly_data_json": json.dumps(weekly_by_day),
        "active_page": "teacher_dashboard",
    }
    return render(request, "teacher_dashboard.html", context)


@role_required("teacher")
def teacher_live_mode_view(request, lesson_id):
    """
    Інтерактивний екран для проведення пари.
    """
    from datetime import date

    from main.models import BuildingAccessLog

    # 1. Отримуємо урок і перевіряємо права
    lesson = get_object_or_404(Lesson, id=lesson_id, teacher=request.user)

    # 2. Отримуємо студентів групи
    students = User.objects.filter(role="student", group=lesson.group).order_by(
        "full_name"
    )

    # 3. Отримуємо вже існуючі оцінки
    performances = StudentPerformance.objects.filter(lesson=lesson).select_related(
        "absence"
    )
    perf_map = {p.student_id: p for p in performances}

    # 4. Отримуємо статус присутності по RFID (за сьогодні)
    today = date.today()
    access_logs = BuildingAccessLog.objects.filter(
        timestamp__date=today, student__in=students
    ).order_by("student", "timestamp")

    in_building_map = {}
    student_logs = {}
    for log in access_logs:
        student_logs[log.student_id] = log
    for s in students:
        last_log = student_logs.get(s.id)
        in_building_map[s.id] = (
            True if last_log and last_log.action == "ENTER" else False
        )

    # 5. Формуємо список для фронтенду
    student_list = []
    for s in students:
        perf = perf_map.get(s.id)

        # Визначаємо статус
        grade_value = None
        comment = ""
        is_in_building = in_building_map.get(s.id, False)

        # Пріоритет:
        # 1. Ручна оцінка/відмітка в БД
        # 2. Якщо немає в БД -> статус по RFID (якщо не в будівлі - відсутній)
        if perf:
            if perf.earned_points is not None:
                grade_value = (
                    int(perf.earned_points)
                    if perf.earned_points % 1 == 0
                    else perf.earned_points
                )
            is_absent = True if perf.absence else False
            comment = perf.comment or ""
        else:
            # Дефолтна логіка: якщо не "пікнувся" — відсутній
            is_absent = not is_in_building

        student_list.append(
            {
                "user": s,
                "grade": grade_value,
                "is_absent": is_absent,
                "comment": comment,
                "initials": "".join([name[0] for name in s.full_name.split()[:2]]),
            }
        )

    context = {
        "lesson": lesson,
        "student_list": student_list,
        "active_page": "teacher_dashboard",
    }
    return render(request, "teacher_live_mode.html", context)


@role_required("student")
def student_dashboard_view(request: HttpRequest) -> HttpResponse:
    """Дашборд студента з аналітикою та розкладом."""
    student = request.user
    from django.utils import timezone

    now_aware = timezone.localtime(timezone.now())
    today = now_aware.date()
    now_time = now_aware.time()

    # 1. Загальна статистика (Середній бал)
    performance_queryset = StudentPerformance.objects.filter(student=student)

    stats = performance_queryset.filter(earned_points__isnull=False).aggregate(
        avg_score=Avg("earned_points")
    )

    # 2. Відвідуваність (для кругової діаграми)
    total_lessons_count = performance_queryset.count()
    absence_stats = performance_queryset.filter(absence__isnull=False).aggregate(
        total_absences=Count("id"),
        respectful=Count("id", filter=Q(absence__is_respectful=True)),
        unrespectful=Count("id", filter=Q(absence__is_respectful=False)),
    )

    present_count = total_lessons_count - (absence_stats["total_absences"] or 0)
    attendance_percent = (
        round((present_count / total_lessons_count * 100), 1)
        if total_lessons_count > 0
        else 0
    )

    # 3. Дані для графіка (останні 30 оцінок)
    chart_data = (
        performance_queryset.filter(earned_points__isnull=False)
        .select_related("lesson", "lesson__subject")
        .order_by("lesson__date", "lesson__start_time")[:30]
    )

    graph_labels = [p.lesson.date.strftime("%d.%m") for p in chart_data]
    graph_points = [float(p.earned_points) for p in chart_data]

    # 4. Уроки (Зараз та Наступний)
    lessons_today = (
        Lesson.objects.filter(group=student.group, date=today)
        .select_related("subject", "classroom", "teacher")
        .order_by("start_time")
    )

    current_lesson = None
    next_lesson = None

    for l in lessons_today:
        if l.start_time <= now_time <= l.end_time:
            current_lesson = l
        elif l.start_time > now_time:
            next_lesson = l
            break

    if not next_lesson:
        # Шукаємо наступний урок у майбутні дні
        next_lesson = (
            Lesson.objects.filter(group=student.group, date__gt=today)
            .select_related("subject", "classroom", "teacher")
            .order_by("date", "start_time")
            .first()
        )

    # 5. Останні події (5 останніх оцінок)
    recent_events = (
        performance_queryset.filter(earned_points__isnull=False)
        .select_related("lesson", "lesson__subject")
        .order_by("-lesson__date", "-lesson__start_time")[:5]
    )

    # 6. Статус входу (RFID)
    last_access = (
        BuildingAccessLog.objects.filter(student=student).order_by("-timestamp").first()
    )
    in_building = (last_access.action == "ENTER") if last_access else False

    context = {
        "avg_score": round(stats["avg_score"] or 0, 1),
        "attendance_percent": attendance_percent,
        "attendance_json": json.dumps(
            {
                "present": present_count,
                "respectful": absence_stats["respectful"] or 0,
                "unrespectful": absence_stats["unrespectful"] or 0,
            }
        ),
        "graph_labels_json": json.dumps(graph_labels),
        "graph_points_json": json.dumps(graph_points),
        "current_lesson": current_lesson,
        "next_lesson": next_lesson,
        "recent_events": recent_events,
        "in_building": in_building,
        "last_access": last_access,
        "active_page": "student_dashboard",
    }
    return render(request, "student_dashboard.html", context)


# =========================
# 5. ЗВІТИ (АДМІН)
# =========================


@role_required("admin")
def admin_reports_view(request):
    return render(request, "admin_reports.html", {"active_page": "reports"})


@role_required("admin")
def report_absences_view(request):
    group_id = request.GET.get("group", "")
    subject_id = request.GET.get("subject", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    limit = int(request.GET.get("limit", 0) or 0)
    is_active = request.GET.get("is_active", "true")

    # Глобальний контекст (якщо фільтри не задані)
    course = request.GET.get("course") or request.session.get("global_course")
    specialty = request.GET.get("specialty") or request.session.get(
        "global_specialty_id"
    )

    students = User.objects.filter(role="student")

    if group_id:
        students = students.filter(group_id=group_id)

    # Фільтр по курсу (через групу)
    if course:
        students = students.filter(group__course=course)

    # Фільтр по спеціальності
    if specialty:
        if str(specialty).isdigit():
            students = students.filter(group__specialty_id=int(specialty))
        else:
            students = students.filter(group__specialty__name__icontains=specialty)

    # Фільтр по статусу активності
    if is_active:
        students = students.filter(is_active=(is_active == "true"))

    perf_filter = Q(studentperformance__absence__isnull=False)

    if subject_id:
        perf_filter &= Q(studentperformance__lesson__subject_id=subject_id)
    if date_from:
        perf_filter &= Q(studentperformance__lesson__date__gte=date_from)
    if date_to:
        perf_filter &= Q(studentperformance__lesson__date__lte=date_to)

    unexcused_filter = perf_filter & Q(studentperformance__absence__is_respectful=False)

    report_data = (
        students.annotate(
            total_absences=Count("studentperformance", filter=perf_filter),
            unexcused_absences=Count("studentperformance", filter=unexcused_filter),
        )
        .filter(total_absences__gt=0)
        .order_by("-total_absences")
    )

    if limit > 0:
        report_data = report_data[:limit]

    for item in report_data:
        item.excused_absences = item.total_absences - item.unexcused_absences

    if request.GET.get("export") == "csv":
        rows = [
            [
                u.full_name,
                u.group.name if u.group else "-",
                u.total_absences,
                u.unexcused_absences,
            ]
            for u in report_data
        ]
        return generate_csv_response(
            f"absences_report_{date.today()}",
            ["ПІБ", "Група", "Всього", "Неповажні"],
            rows,
        )

    groups = StudyGroup.objects.all()
    all_subjects = Subject.objects.all()

    # Отримуємо унікальні спеціальності та курси
    specialties = (
        StudyGroup.objects.exclude(specialty=None)
        .values_list("specialty__name", flat=True)
        .distinct()
    )
    courses = (
        StudyGroup.objects.exclude(course__isnull=True)
        .values_list("course", flat=True)
        .distinct()
        .order_by("course")
    )

    context = {
        "report_data": report_data,
        "report_title": "Звіт: Пропуски студентів",
        "is_absences_report": True,
        "is_weekly_report": False,
        "report_reset_url_name": "report_absences",
        "groups": groups,
        "all_subjects": all_subjects,
        "specialties": specialties,
        "courses": courses,
        "active_page": "reports",
    }
    return render(request, "report_absences.html", context)


@role_required("admin")
def report_rating_view(request):
    group_id = request.GET.get("group", "")
    subject_id = request.GET.get("subject", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    # Нові фільтри (з підтримкою глобального контексту)
    course = request.GET.get("course") or request.session.get("global_course")
    specialty = request.GET.get("specialty") or request.session.get(
        "global_specialty_id"
    )
    is_active = request.GET.get("is_active", "true")

    MIN_VOTES = 5

    perf_base_filter = Q(earned_points__isnull=False)
    perf_user_filter = Q(studentperformance__earned_points__isnull=False)

    if subject_id:
        term = Q(lesson__subject_id=subject_id)
        perf_base_filter &= term
        perf_user_filter &= Q(studentperformance__lesson__subject_id=subject_id)
    if date_from:
        term = Q(lesson__date__gte=date_from)
        perf_base_filter &= term
        perf_user_filter &= Q(studentperformance__lesson__date__gte=date_from)
    if date_to:
        term = Q(lesson__date__lte=date_to)
        perf_base_filter &= term
        perf_user_filter &= Q(studentperformance__lesson__date__lte=date_to)

    global_stats = (
        StudentPerformance.objects.filter(perf_base_filter)
        .annotate(
            weighted_val=F("earned_points")
            * F("lesson__evaluation_type__weight_percent")
        )
        .aggregate(
            total_weighted=Sum("weighted_val"),
            total_weights=Sum("lesson__evaluation_type__weight_percent"),
        )
    )

    C_sum = float(global_stats["total_weighted"] or 0)
    C_weight = float(global_stats["total_weights"] or 1)
    C = C_sum / C_weight if C_weight > 0 else 0

    students_query = User.objects.filter(role="student")
    if group_id:
        students_query = students_query.filter(group_id=group_id)

    # Нові фільтри
    if course:
        students_query = students_query.filter(group__course=course)
    if specialty:
        if str(specialty).isdigit():
            students_query = students_query.filter(group__specialty_id=int(specialty))
        else:
            students_query = students_query.filter(
                group__specialty__name__icontains=specialty
            )
    if is_active:
        students_query = students_query.filter(is_active=(is_active == "true"))

    students_data = students_query.annotate(
        v=Count("studentperformance", filter=perf_user_filter),
        weighted_sum=Sum(
            F("studentperformance__earned_points")
            * F("studentperformance__lesson__evaluation_type__weight_percent"),
            filter=perf_user_filter,
        ),
        weight_total=Sum(
            F("studentperformance__lesson__evaluation_type__weight_percent"),
            filter=perf_user_filter,
        ),
    ).filter(v__gt=0)

    rating_list = []

    for student in students_data:
        v = student.v
        ws = float(student.weighted_sum or 0)
        wt = float(student.weight_total or 1)

        R = ws / wt if wt > 0 else 0

        weighted_rating = (v / (v + MIN_VOTES)) * R + (
            MIN_VOTES / (v + MIN_VOTES)
        ) * float(C)

        group_name = student.group.name if student.group else "-"

        rating_list.append(
            {
                "full_name": student.full_name,
                "group": {"name": group_name},
                "raw_avg": round(R, 2),
                "count": v,
                "weighted_avg": round(weighted_rating, 2),
            }
        )

    rating_list.sort(key=lambda x: x["weighted_avg"], reverse=True)

    if request.GET.get("export") == "csv":
        rows = [
            [
                r["full_name"],
                r["group"]["name"],
                r["raw_avg"],
                r["weighted_avg"],
                r["count"],
            ]
            for r in rating_list
        ]
        return generate_csv_response(
            f"rating_bayesian_{date.today()}",
            ["ПІБ", "Група", "Середній бал", "Рейтинг (Зважений)", "К-сть оцінок"],
            rows,
        )

    groups = StudyGroup.objects.all()
    all_subjects = Subject.objects.all()

    # Отримуємо унікальні спеціальності та курси
    specialties = (
        StudyGroup.objects.exclude(specialty=None)
        .values_list("specialty__name", flat=True)
        .distinct()
    )
    courses = (
        StudyGroup.objects.exclude(course__isnull=True)
        .values_list("course", flat=True)
        .distinct()
        .order_by("course")
    )

    context = {
        "report_data": rating_list,
        "report_title": "Звіт: Рейтинг студентів",
        "is_rating_report": True,
        "is_weekly_report": False,
        "report_reset_url_name": "report_rating",
        "groups": groups,
        "all_subjects": all_subjects,
        "specialties": specialties,
        "courses": courses,
        "active_page": "reports",
    }
    return render(request, "report_absences.html", context)


@role_required("admin")
def report_weekly_absences_view(request):
    group_id = request.GET.get("group", "")
    subject_id = request.GET.get("subject", "")

    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)

    students = User.objects.filter(role="student")
    if group_id:
        students = students.filter(group_id=group_id)

    perf_filter = Q(
        studentperformance__absence__isnull=False,
        studentperformance__lesson__date__gte=start_week,
        studentperformance__lesson__date__lte=end_week,
    )

    if subject_id:
        perf_filter &= Q(studentperformance__lesson__subject_id=subject_id)

    unexcused_filter = perf_filter & Q(studentperformance__absence__is_respectful=False)

    report_data = (
        students.annotate(
            total_absences=Count("studentperformance", filter=perf_filter),
            unexcused_absences=Count("studentperformance", filter=unexcused_filter),
        )
        .filter(total_absences__gt=0)
        .order_by("-total_absences")
    )

    groups = StudyGroup.objects.all()
    all_subjects = Subject.objects.all()

    context = {
        "report_data": report_data,
        "report_title": f"Звіт: Пропуски за тиждень ({start_week} - {end_week})",
        "is_absences_report": True,
        "is_weekly_report": True,
        "report_reset_url_name": "report_weekly_absences",
        "groups": groups,
        "all_subjects": all_subjects,
        "active_page": "reports",
    }
    return render(request, "report_absences.html", context)


@role_required("admin")
def report_subjects_view(request):
    """Звіт: Успішність по предметах — середній бал, кількість студентів, відсоток успішних."""
    course = request.GET.get("course") or request.session.get("global_course")
    specialty = request.GET.get("specialty") or request.session.get(
        "global_specialty_id"
    )

    subjects_qs = Subject.objects.all()
    if course or specialty:
        ta_filter = Q()
        if course:
            ta_filter &= Q(teachingassignment__group__course=course)
        if specialty:
            if str(specialty).isdigit():
                ta_filter &= Q(teachingassignment__group__specialty_id=int(specialty))
            else:
                ta_filter &= Q(
                    teachingassignment__group__specialty__name__icontains=specialty
                )
        subjects_qs = subjects_qs.filter(ta_filter).distinct()

    report_data = []
    for subject in subjects_qs:
        perf_qs = StudentPerformance.objects.filter(
            lesson__subject=subject,
            earned_points__isnull=False,
        )
        if course:
            perf_qs = perf_qs.filter(student__group__course=course)
        if specialty:
            if str(specialty).isdigit():
                perf_qs = perf_qs.filter(student__group__specialty_id=int(specialty))
            else:
                perf_qs = perf_qs.filter(
                    student__group__specialty__name__icontains=specialty
                )

        stats = perf_qs.aggregate(
            avg_pts=Avg("earned_points"),
            total=Count("id"),
            lesson_count=Count("lesson_id", distinct=True),
            student_count=Count("student_id", distinct=True),
        )
        if not stats["total"]:
            continue

        passing = perf_qs.filter(
            earned_points__gte=F("lesson__max_points") * 0.6
        ).count()

        report_data.append(
            {
                "name": subject.name,
                "credits": subject.credits,
                "lesson_count": stats["lesson_count"] or 0,
                "student_count": stats["student_count"] or 0,
                "avg_points": round(float(stats["avg_pts"] or 0), 2),
                "grade_count": stats["total"] or 0,
                "pass_rate": (
                    round(passing / stats["total"] * 100, 1) if stats["total"] else 0
                ),
            }
        )

    report_data.sort(key=lambda x: x["avg_points"], reverse=True)

    if request.GET.get("export") == "csv":
        rows = [
            [
                r["name"],
                r["credits"],
                r["lesson_count"],
                r["student_count"],
                r["avg_points"],
                f"{r['pass_rate']}%",
            ]
            for r in report_data
        ]
        return generate_csv_response(
            f"subjects_report_{date.today()}",
            ["Предмет", "ECTS", "Занять", "Студентів", "Сер. бал", "% успішних"],
            rows,
        )

    specialties = (
        StudyGroup.objects.exclude(specialty=None)
        .values_list("specialty__name", flat=True)
        .distinct()
    )
    courses = (
        StudyGroup.objects.exclude(course__isnull=True)
        .values_list("course", flat=True)
        .distinct()
        .order_by("course")
    )

    context = {
        "report_data": report_data,
        "report_title": "Звіт: Успішність по предметах",
        "specialties": specialties,
        "courses": courses,
        "active_page": "reports",
    }
    return render(request, "report_subjects.html", context)


@role_required("admin")
def report_at_risk_view(request):
    """Звіт: Студенти в зоні ризику — поєднання низьких оцінок та пропусків."""
    group_id = request.GET.get("group", "")
    course = request.GET.get("course") or request.session.get("global_course")
    specialty = request.GET.get("specialty") or request.session.get(
        "global_specialty_id"
    )
    absence_threshold = int(request.GET.get("absence_threshold", 3) or 3)
    grade_threshold = float(request.GET.get("grade_threshold", 60) or 60)

    students = User.objects.filter(role="student", is_active=True)
    if group_id:
        students = students.filter(group_id=group_id)
    if course:
        students = students.filter(group__course=course)
    if specialty:
        if str(specialty).isdigit():
            students = students.filter(group__specialty_id=int(specialty))
        else:
            students = students.filter(group__specialty__name__icontains=specialty)

    absence_filter = Q(studentperformance__absence__isnull=False)
    unexcused_filter = absence_filter & Q(
        studentperformance__absence__is_respectful=False
    )
    grade_filter = Q(studentperformance__earned_points__isnull=False)

    students = students.annotate(
        total_absences=Count("studentperformance", filter=absence_filter),
        unexcused_absences=Count("studentperformance", filter=unexcused_filter),
        avg_grade=Avg("studentperformance__earned_points", filter=grade_filter),
        grade_count=Count("studentperformance", filter=grade_filter),
    ).select_related("group")

    report_data = []
    for student in students:
        avg = float(student.avg_grade or 0)
        unexcused = student.unexcused_absences

        has_absence_risk = unexcused >= absence_threshold
        has_grade_risk = student.grade_count > 0 and avg < grade_threshold

        if not has_absence_risk and not has_grade_risk:
            continue

        risk_level = "high" if (has_absence_risk and has_grade_risk) else "medium"
        report_data.append(
            {
                "full_name": student.full_name,
                "group": student.group,
                "avg_grade": round(avg, 1),
                "total_absences": student.total_absences,
                "unexcused_absences": unexcused,
                "grade_count": student.grade_count,
                "risk_level": risk_level,
                "has_absence_risk": has_absence_risk,
                "has_grade_risk": has_grade_risk,
            }
        )

    report_data.sort(
        key=lambda x: (0 if x["risk_level"] == "high" else 1, -x["unexcused_absences"])
    )

    if request.GET.get("export") == "csv":
        rows = [
            [
                r["full_name"],
                r["group"].name if r["group"] else "-",
                r["avg_grade"],
                r["total_absences"],
                r["unexcused_absences"],
                "Критичний" if r["risk_level"] == "high" else "Помірний",
            ]
            for r in report_data
        ]
        return generate_csv_response(
            f"at_risk_report_{date.today()}",
            [
                "ПІБ",
                "Група",
                "Сер. бал",
                "Всього пропусків",
                "Неповажні",
                "Рівень ризику",
            ],
            rows,
        )

    groups = StudyGroup.objects.all()
    specialties = (
        StudyGroup.objects.exclude(specialty=None)
        .values_list("specialty__name", flat=True)
        .distinct()
    )
    courses = (
        StudyGroup.objects.exclude(course__isnull=True)
        .values_list("course", flat=True)
        .distinct()
        .order_by("course")
    )

    context = {
        "report_data": report_data,
        "report_title": "Звіт: Студенти в зоні ризику",
        "groups": groups,
        "specialties": specialties,
        "courses": courses,
        "absence_threshold": absence_threshold,
        "grade_threshold": grade_threshold,
        "active_page": "reports",
    }
    return render(request, "report_at_risk.html", context)


# =========================
# 5. EVALUATION TYPES MANAGEMENT
# =========================


@role_required("teacher")
def manage_evaluation_types_view(request):
    teacher_id = request.user.id  # request.user

    assignments = TeachingAssignment.objects.filter(
        teacher_id=teacher_id
    ).select_related("subject", "group")

    selected_assignment_id = request.GET.get("assignment")
    selected_assignment = None
    evaluation_types = []
    total_weight = 0

    if selected_assignment_id:
        try:
            selected_assignment = assignments.get(id=selected_assignment_id)
            evaluation_types = EvaluationType.objects.filter(
                assignment=selected_assignment
            ).order_by("name")
            total_weight = sum(et.weight_percent for et in evaluation_types)
        except TeachingAssignment.DoesNotExist:
            messages.error(request, "Призначення не знайдено")

    if request.method == "POST":
        if not selected_assignment:
            messages.error(request, "Спочатку оберіть предмет та групу")
            return redirect("manage_evaluation_types")

        from .forms import EvaluationTypeForm

        form = EvaluationTypeForm(request.POST)

        if form.is_valid():
            eval_type = form.save(commit=False)
            eval_type.assignment = selected_assignment

            current_total = sum(et.weight_percent for et in evaluation_types)
            new_total = current_total + eval_type.weight_percent

            if new_total > 100:
                messages.error(
                    request,
                    f"Сума ваг не може перевищувати 100%. Поточна сума: {current_total}%, спроба додати: {eval_type.weight_percent}%",
                )
            else:
                eval_type.save()
                messages.success(
                    request, f"Тип оцінювання '{eval_type.name}' додано успішно"
                )
                return redirect(
                    f"manage_evaluation_types?assignment={selected_assignment.id}"
                )
        else:
            messages.error(request, "Помилка при додаванні типу оцінювання")

    from .forms import EvaluationTypeForm

    form = EvaluationTypeForm()

    context = {
        "assignments": assignments,
        "selected_assignment": selected_assignment,
        "selected_assignment_id": selected_assignment_id,
        "evaluation_types": evaluation_types,
        "total_weight": total_weight,
        "form": form,
        "active_page": "teacher",
    }
    return render(request, "evaluation_types_config.html", context)


@role_required("teacher")
@require_POST
def evaluation_type_edit_view(request, pk):
    teacher_id = request.user.id
    eval_type = get_object_or_404(EvaluationType, pk=pk)

    if eval_type.assignment.teacher_id != teacher_id:
        messages.error(request, "У вас немає прав для редагування цього типу")
        return redirect("manage_evaluation_types")

    name = request.POST.get("name")
    weight_percent = request.POST.get("weight_percent")

    try:
        weight_percent = float(weight_percent)

        other_types = EvaluationType.objects.filter(
            assignment=eval_type.assignment
        ).exclude(pk=pk)
        other_total = sum(et.weight_percent for et in other_types)
        new_total = other_total + weight_percent

        if new_total > 100:
            messages.error(
                request,
                f"Сума ваг не може перевищувати 100%. Сума інших типів: {other_total}%",
            )
        elif weight_percent < 0:
            messages.error(request, "Вага не може бути від'ємною")
        else:
            eval_type.name = name
            eval_type.weight_percent = weight_percent
            eval_type.save()
            messages.success(request, "Тип оцінювання оновлено")
    except (ValueError, TypeError):
        messages.error(request, "Некоректне значення ваги")

    return redirect(f"manage_evaluation_types?assignment={eval_type.assignment.id}")


@role_required("teacher")
@require_POST
def evaluation_type_delete_view(request, pk):
    teacher_id = request.user.id
    eval_type = get_object_or_404(EvaluationType, pk=pk)

    if eval_type.assignment.teacher_id != teacher_id:
        messages.error(request, "У вас немає прав для видалення цього типу")
        return redirect("manage_evaluation_types")

    assignment_id = eval_type.assignment.id

    if Lesson.objects.filter(evaluation_type=eval_type).exists():
        messages.error(
            request,
            "Неможливо видалити тип оцінювання, оскільки він використовується в занятях",
        )
    else:
        eval_type.delete()
        messages.success(request, "Тип оцінювання видалено")

    return redirect(f"manage_evaluation_types?assignment={assignment_id}")


@role_required("teacher")
def get_evaluation_types_api(request):
    assignment_id = request.GET.get("assignment_id")

    if not assignment_id:
        return JsonResponse({"error": "assignment_id обов'язковий"}, status=400)

    teacher_id = request.user.id

    try:
        assignment = TeachingAssignment.objects.get(
            id=assignment_id, teacher_id=teacher_id
        )

        evaluation_types = EvaluationType.objects.filter(assignment=assignment).values(
            "id", "name", "weight_percent"
        )

        return JsonResponse({"evaluation_types": list(evaluation_types)})
    except TeachingAssignment.DoesNotExist:
        return JsonResponse({"error": "Призначення не знайдено"}, status=404)


# --- STUDENTS MANAGEMENT (EXTRA) ---


@login_required
def timeline_schedule_view(request):
    user = request.user

    # Визначаємо групу
    group = user.group if user.role == "student" else None
    if not group and request.GET.get("group_id"):
        group = get_object_or_404(StudyGroup, id=request.GET.get("group_id"))

    # Дні тижня
    days_data = []
    days_names = {
        1: "Понеділок",
        2: "Вівторок",
        3: "Середа",
        4: "Четвер",
        5: "П'ятниця",
    }

    # TIMEZONE FIX
    from django.utils import timezone

    now_aware = timezone.localtime(timezone.now())
    current_time_minutes = now_aware.hour * 60 + now_aware.minute
    current_day = now_aware.weekday() + 1  # 1=Monday

    if group:
        # Дні тижня для таймлайну
        today_date = now_aware.date()
        start_week = today_date - timedelta(days=today_date.weekday())

        for day_num, day_name in days_names.items():
            day_lessons = []
            current_day_date = start_week + timedelta(days=day_num - 1)

            # Беремо реальні уроки з БД, відсортовані за часом початку
            lessons_in_db = (
                Lesson.objects.filter(group=group, date=current_day_date)
                .select_related("subject", "teacher", "classroom")
                .order_by("start_time")
            )

            for lesson_idx, lesson in enumerate(lessons_in_db, start=1):
                start_min = lesson.start_time.hour * 60 + lesson.start_time.minute
                end_min = lesson.end_time.hour * 60 + lesson.end_time.minute
                duration = end_min - start_min

                status = "future"
                progress = 0

                if day_num < current_day:
                    status = "past"
                elif day_num == current_day:
                    if current_time_minutes > end_min:
                        status = "past"
                    elif current_time_minutes >= start_min:
                        status = "current"
                        passed = current_time_minutes - start_min
                        progress = int((passed / duration) * 100) if duration > 0 else 0

                # Псевдо-слот: формуємо з часів самого уроку
                pseudo_slot = {
                    "start_time": lesson.start_time,
                    "end_time": lesson.end_time,
                    "lesson_number": lesson_idx,
                }

                day_lessons.append(
                    {
                        "slot": pseudo_slot,
                        "assignment": lesson,
                        "status": status,
                        "progress": min(max(progress, 0), 100),
                        "duration": duration,
                    }
                )

            days_data.append(
                {
                    "day_name": day_name,
                    "is_today": day_num == current_day,
                    "lessons": day_lessons,
                }
            )

    return render(
        request,
        "timeline_schedule.html",
        {
            "days_data": days_data,
            "group": group,
            "all_groups": (
                StudyGroup.objects.all().order_by("name")
                if user.role != "student"
                else None
            ),
            "active_page": "schedule",
        },
    )


@require_POST
@role_required("teacher")
def api_update_lesson(request: HttpRequest) -> JsonResponse:
    """API для оновлення деталей уроку."""
    try:
        data = json.loads(request.body)
        lesson_id = data.get("lesson_id")
        topic = data.get("topic")
        type_id = data.get("type_id")

        is_cancelled = data.get("is_cancelled")
        cancellation_reason = data.get("cancellation_reason")

        eval_weight = data.get("eval_weight")

        lesson = get_object_or_404(Lesson, id=lesson_id, teacher=request.user)

        if topic is not None:
            lesson.topic = topic

        if type_id:
            etype = get_object_or_404(
                EvaluationType, id=type_id, assignment__teacher=request.user
            )
            lesson.evaluation_type = etype
            if eval_weight is not None:
                try:
                    weight = float(eval_weight)
                    if 0 <= weight <= 100:
                        etype.weight_percent = weight
                        etype.save(update_fields=["weight_percent", "updated_at"])
                except (ValueError, TypeError):
                    pass

        if is_cancelled is not None:
            lesson.is_cancelled = bool(is_cancelled)
            if lesson.is_cancelled and cancellation_reason is not None:
                lesson.cancellation_reason = cancellation_reason
            elif not lesson.is_cancelled:
                lesson.cancellation_reason = ""

        lesson.save()

        logger.info(f"Викладач {request.user} оновив урок #{lesson_id}")

        etype = lesson.evaluation_type
        return JsonResponse(
            {
                "status": "success",
                "topic": lesson.topic,
                "type_name": etype.name if etype else "—",
                "max_points": float(etype.weight_percent) if etype else 12,
                "eval_weight": float(etype.weight_percent) if etype else None,
                "is_cancelled": lesson.is_cancelled,
                "cancellation_reason": lesson.cancellation_reason or "",
            }
        )

    except Exception as e:
        import traceback

        print(traceback.format_exc())
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@role_required("teacher")
def teacher_settings_view(request: HttpRequest) -> HttpResponse:
    """Сторінка налаштувань викладача для керування типами занять."""
    teacher = request.user
    assignments = TeachingAssignment.objects.filter(teacher=teacher).select_related(
        "subject", "group"
    )

    settings_data = []
    for a in assignments:
        types = a.evaluation_types.all()
        settings_data.append({"assignment": a, "types": types})

    return render(
        request,
        "teacher_settings.html",
        {"settings_data": settings_data, "active_page": "teacher"},
    )


@require_POST
@role_required("teacher")
def api_manage_evaluation_types(request: HttpRequest) -> JsonResponse:
    """API для CRUD операцій над EvaluationType."""
    try:
        data = json.loads(request.body)
        action = data.get("action")

        if action == "create":
            assignment_id = data.get("assignment_id")
            name = data.get("name")
            weight = data.get("weight", 0)

            assignment = get_object_or_404(
                TeachingAssignment, id=assignment_id, teacher=request.user
            )
            etype = EvaluationType.objects.create(
                assignment=assignment, name=name, weight_percent=weight
            )
            return JsonResponse({"status": "success", "id": etype.id})

        elif action == "update":
            type_id = data.get("id")
            name = data.get("name")
            weight = data.get("weight")

            etype = get_object_or_404(
                EvaluationType, id=type_id, assignment__teacher=request.user
            )
            etype.name = name
            etype.weight_percent = weight
            etype.save()
            return JsonResponse({"status": "success"})

        elif action == "delete":
            type_id = data.get("id")
            etype = get_object_or_404(
                EvaluationType, id=type_id, assignment__teacher=request.user
            )

            if Lesson.objects.filter(evaluation_type=etype).exists():
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "Цей тип вже використовується в уроках і не може бути видалений.",
                    },
                    status=400,
                )

            etype.delete()
            return JsonResponse({"status": "success"})

        return JsonResponse(
            {"status": "error", "message": "Unknown action"}, status=400
        )

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# =========================
# 6. ПРОФІЛЬ ТА НАЛАШТУВАННЯ
# =========================


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """Сторінка профілю користувача та налаштувань."""
    user = request.user
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профіль успішно оновлено!")
            return redirect("profile")
        else:
            messages.error(request, "Помилка при оновленні профілю.")
    else:
        form = ProfileForm(instance=user)

    context = {
        "user": user,
        "form": form,
        "active_page": "profile",
    }
    return render(request, "profile.html", context)


@login_required
@require_POST
def api_set_theme(request: HttpRequest) -> JsonResponse:
    """Зберігає вибрану тему інтерфейсу для користувача."""
    theme = request.POST.get("theme", "light")
    if theme in ("light", "dark"):
        request.user.theme = theme
        request.user.save(update_fields=["theme"])
        return JsonResponse({"status": "ok", "theme": theme})
    return JsonResponse({"status": "error", "message": "Invalid theme"}, status=400)


# =========================
# СТРІЧКА НОВИН
# =========================


@login_required
def news_feed_view(request: HttpRequest) -> HttpResponse:
    user = request.user

    # Визначаємо групи, доступні користувачеві
    if user.role == "admin":
        group_ids = list(StudyGroup.objects.values_list("id", flat=True))
        teacher_groups = StudyGroup.objects.all().order_by("name")
    elif user.role == "teacher":
        group_ids = list(
            TeachingAssignment.objects.filter(teacher=user, is_active=True)
            .values_list("group_id", flat=True)
            .distinct()
        )
        teacher_groups = StudyGroup.objects.filter(id__in=group_ids).order_by("name")
    else:  # student
        group_ids = [user.group_id] if user.group_id else []
        teacher_groups = None

    # Загальні пости + пости для дозволених груп
    posts = (
        Post.objects.filter(Q(post_type="general") | Q(group_id__in=group_ids))
        .select_related("author", "group")
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("author").order_by(
                    "created_at"
                ),
            )
        )
        .order_by("-created_at")
    )

    # Фільтрація за вкладкою
    tab = request.GET.get("tab", "all")
    if tab == "general":
        posts = posts.filter(post_type="general")
    elif tab == "group" and user.role == "student":
        posts = posts.filter(post_type="group", group_id=user.group_id)
    elif tab.startswith("group_") and user.role in ("teacher", "admin"):
        try:
            gid = int(tab.split("_", 1)[1])
            posts = posts.filter(post_type="group", group_id=gid)
        except (ValueError, IndexError):
            pass

    context = {
        "posts": posts,
        "teacher_groups": teacher_groups,
        "group_ids": group_ids,
        "active_tab": tab,
        "active_page": "news",
        "student_group": user.group if user.role == "student" else None,
    }
    return render(request, "news_feed.html", context)


@login_required
@require_POST
def api_news_create_post(request: HttpRequest) -> JsonResponse:
    if request.user.role not in ("teacher", "admin"):
        return JsonResponse({"error": "Немає прав"}, status=403)

    post_type = request.POST.get("post_type", "general")
    group_id = request.POST.get("group_id") or None
    title = request.POST.get("title", "").strip()
    content = request.POST.get("content", "").strip()

    if not content:
        return JsonResponse(
            {"error": "Текст допису не може бути порожнім."}, status=400
        )

    if post_type == "group":
        if not group_id:
            return JsonResponse({"error": "Оберіть групу."}, status=400)
        # Перевіряємо доступ викладача до цієї групи
        if request.user.role == "teacher":
            has_access = TeachingAssignment.objects.filter(
                teacher=request.user, group_id=group_id, is_active=True
            ).exists()
            if not has_access:
                return JsonResponse(
                    {"error": "Немає доступу до цієї групи."}, status=403
                )
        group = get_object_or_404(StudyGroup, id=group_id)
    else:
        group = None

    post = Post.objects.create(
        author=request.user,
        post_type=post_type,
        group=group,
        title=title,
        content=content,
    )

    # --- Сповіщення про нову публікацію ---
    role_label = "Адміністратор" if request.user.role == "admin" else "Викладач"
    author_label = f"{request.user.full_name} ({role_label})"
    notif_title = post.title or content[:60]
    if post_type == "general":
        recipients = list(
            User.objects.filter(role__in=["student", "teacher"]).exclude(
                id=request.user.id
            )
        )
    else:
        student_recips = list(User.objects.filter(role="student", group=group))
        teacher_recips = list(
            User.objects.filter(
                role="teacher",
                teachingassignment__group=group,
                teachingassignment__is_active=True,
            )
            .exclude(id=request.user.id)
            .distinct()
        )
        recipients = student_recips + teacher_recips
    Notification.objects.bulk_create(
        [
            Notification(
                recipient=u,
                notif_type="news",
                title=f"Нова публікація від {author_label}",
                message=notif_title,
                post=post,
            )
            for u in recipients
        ]
    )

    return JsonResponse(
        {
            "id": post.id,
            "author": post.author.full_name,
            "post_type": post.post_type,
            "group_name": post.group.name if post.group else None,
            "title": post.title,
            "content": post.content,
            "created_at": post.created_at.strftime("%d.%m.%Y %H:%M"),
        }
    )


@login_required
@require_POST
def api_news_create_comment(request: HttpRequest) -> JsonResponse:
    post_id = request.POST.get("post_id")
    content = request.POST.get("content", "").strip()

    if not content:
        return JsonResponse({"error": "Коментар не може бути порожнім."}, status=400)

    post = get_object_or_404(Post, id=post_id)

    # Студент може коментувати лише пости, до яких має доступ
    if request.user.role == "student":
        if post.post_type == "group" and post.group_id != request.user.group_id:
            return JsonResponse({"error": "Немає доступу."}, status=403)

    comment = Comment.objects.create(
        post=post,
        author=request.user,
        content=content,
    )

    # --- Сповіщення автору допису про новий коментар ---
    if post.author != request.user:
        _role_labels = {
            "admin": "Адміністратор",
            "teacher": "Викладач",
            "student": "Студент",
        }
        _role_label = _role_labels.get(request.user.role, "")
        post_label = post.title or post.content[:40]
        Notification.objects.create(
            recipient=post.author,
            notif_type="comment",
            title=f"{request.user.full_name} ({_role_label}) прокоментував(ла) вашу публікацію",
            message=f'"{post_label}": {content[:80]}',
            post=post,
        )

    return JsonResponse(
        {
            "id": comment.id,
            "author": comment.author.full_name,
            "author_role": comment.author.role,
            "content": comment.content,
            "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M"),
        }
    )


@login_required
@require_POST
def api_news_delete_post(request: HttpRequest, pk: int) -> JsonResponse:
    post = get_object_or_404(Post, id=pk)
    if request.user != post.author and request.user.role != "admin":
        return JsonResponse({"error": "Немає прав"}, status=403)
    post.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def api_news_delete_comment(request: HttpRequest, pk: int) -> JsonResponse:
    comment = get_object_or_404(Comment, id=pk)
    if request.user != comment.author and request.user.role != "admin":
        return JsonResponse({"error": "Немає прав"}, status=403)
    comment.delete()
    return JsonResponse({"ok": True})


# =========================
# СПОВІЩЕННЯ
# =========================


def _build_notif_link(n) -> str:
    """Повертає URL для переходу за сповіщенням."""
    if n.link:
        return n.link
    if n.lesson_id:
        return f"/lesson/{n.lesson_id}/"
    if n.post_id:
        return f"/news/#post-{n.post_id}"
    return ""


@login_required
def api_notifications_list(request: HttpRequest) -> JsonResponse:
    """Повертає останні 50 сповіщень поточного користувача."""
    notifications = Notification.objects.filter(recipient=request.user).order_by(
        "-created_at"
    )[:50]
    unread_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()

    TYPE_ICONS = {
        "news": "📢",
        "comment": "💬",
        "grade": "📊",
        "absence": "⚠️",
        "homework": "📝",
        "private_chat": "🔒",
    }

    data = [
        {
            "id": n.id,
            "type": n.notif_type,
            "icon": TYPE_ICONS.get(n.notif_type, "🔔"),
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%d.%m.%Y %H:%M"),
            "link": _build_notif_link(n),
        }
        for n in notifications
    ]
    return JsonResponse({"notifications": data, "unread_count": unread_count})


@login_required
@require_POST
def api_notifications_mark_read(request: HttpRequest, pk: int) -> JsonResponse:
    """Позначає одне сповіщення як прочитане."""
    Notification.objects.filter(id=pk, recipient=request.user).update(is_read=True)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def api_notifications_mark_unread(request: HttpRequest, pk: int) -> JsonResponse:
    """Позначає одне сповіщення як непрочитане."""
    Notification.objects.filter(id=pk, recipient=request.user).update(is_read=False)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def api_notifications_mark_all_read(request: HttpRequest) -> JsonResponse:
    """Позначає всі сповіщення поточного користувача як прочитані."""
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True
    )
    return JsonResponse({"ok": True})


@login_required
@require_POST
def api_notifications_delete(request: HttpRequest, pk: int) -> JsonResponse:
    """Видаляє одне сповіщення."""
    Notification.objects.filter(id=pk, recipient=request.user).delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def api_notifications_delete_all_read(request: HttpRequest) -> JsonResponse:
    """Видаляє всі прочитані сповіщення поточного користувача."""
    Notification.objects.filter(recipient=request.user, is_read=True).delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def api_notifications_delete_all(request: HttpRequest) -> JsonResponse:
    """Видаляє всі сповіщення поточного користувача."""
    Notification.objects.filter(recipient=request.user).delete()
    return JsonResponse({"ok": True})


# =========================
# RFID УПРАВЛІННЯ КАРТКАМИ
# =========================

# File-based store so multiple server processes (runserver on different interfaces) share state
import os as _os

_RFID_STATE_FILE = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    ".rfid_scan_state.json",
)


def _rfid_read_state() -> dict:
    """Read scan state from shared file."""
    try:
        with open(_RFID_STATE_FILE, "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"active": False, "uid": None, "scanned_at": None}


def _rfid_write_state(state: dict):
    """Write scan state to shared file."""
    try:
        with open(_RFID_STATE_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(state))
    except OSError:
        pass


@role_required("admin")
def rfid_management_view(request: HttpRequest) -> HttpResponse:
    """Сторінка управління RFID картками студентів."""
    course_ctx = request.session.get("global_course")
    specialty_ctx = request.session.get("global_specialty_id")

    students = (
        User.objects.filter(role="student")
        .select_related("group")
        .order_by("full_name")
    )

    if course_ctx:
        students = students.filter(group__course=course_ctx)
    if specialty_ctx:
        students = students.filter(group__specialty_id=specialty_ctx)

    context = {
        "students": students,
        "active_page": "rfid",
    }
    return render(request, "rfid_management.html", context)


def api_rfid_presence(request: HttpRequest) -> JsonResponse:
    """GET /api/rfid/presence/?group=<id> — поточна присутність студентів групи."""
    import datetime as _dt

    from django.utils import timezone

    group_id = request.GET.get("group")
    if not group_id:
        return JsonResponse({"error": "group required"}, status=400)

    now = timezone.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + _dt.timedelta(days=1)
    students = User.objects.filter(group_id=group_id, role="student")

    logs = BuildingAccessLog.objects.filter(
        timestamp__gte=day_start, timestamp__lt=day_end, student__in=students
    ).order_by("student_id", "timestamp")
    last_log = {}
    for log in logs:
        last_log[log.student_id] = log.action

    presence = {s.id: last_log.get(s.id) == "ENTER" for s in students}
    return JsonResponse({"presence": presence})


@csrf_exempt
@require_POST
def api_rfid_scan(request: HttpRequest) -> JsonResponse:
    """
    Endpoint для ESP32: приймає uid від зчитувача.
    Якщо scan_mode активний — зберігає у буфер і повертає {"mode": "assign"}.
    Інакше — стандартна логіка вхід/вихід.
    """
    try:
        data = json.loads(request.body)
        uid = data.get("uid", "").strip().upper()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not uid:
        return JsonResponse({"error": "No UID"}, status=400)

    state = _rfid_read_state()

    # Якщо режим призначення активний — зберігаємо UID у буфер
    if state.get("active"):
        state["uid"] = uid
        state["scanned_at"] = datetime.now().isoformat()
        _rfid_write_state(state)
        return JsonResponse({"mode": "assign", "uid": uid, "direction": None})

    # Стандартна логіка: вхід/вихід
    try:
        student = User.objects.get(rfid_uid=uid, role="student")
    except User.DoesNotExist:
        return JsonResponse({"error": "unknown_card", "uid": uid}, status=404)

    last_log = (
        BuildingAccessLog.objects.filter(student=student).order_by("-timestamp").first()
    )
    if last_log and last_log.action == "ENTER":
        action = "EXIT"
        direction = "out"
    else:
        action = "ENTER"
        direction = "in"

    BuildingAccessLog.objects.create(student=student, action=action)
    return JsonResponse(
        {
            "mode": "attendance",
            "direction": direction,
            "student": student.full_name,
            "uid": uid,
        }
    )


@login_required
def api_rfid_status(request: HttpRequest) -> JsonResponse:
    """Повертає останній зісканований UID з буферу (polling від адмін-сторінки)."""
    state = _rfid_read_state()
    return JsonResponse(
        {
            "uid": state.get("uid"),
            "scanned_at": state.get("scanned_at"),
            "scan_mode": state.get("active", False),
        }
    )


@role_required("admin")
@require_POST
def api_card_scan(request: HttpRequest) -> JsonResponse:
    """
    Вмикає/вимикає режим сканування картки для адмін-сторінки.
    POST {"action": "start"} — активує режим, очищає буфер.
    POST {"action": "stop"}  — деактивує режим.
    """
    try:
        data = json.loads(request.body)
        action = data.get("action", "")
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if action == "start":
        _rfid_write_state({"active": True, "uid": None, "scanned_at": None})
        return JsonResponse({"ok": True, "scan_mode": True})
    elif action == "stop":
        _rfid_write_state({"active": False, "uid": None, "scanned_at": None})
        return JsonResponse({"ok": True, "scan_mode": False})

    return JsonResponse({"error": "Unknown action"}, status=400)


@role_required("admin")
@require_POST
def api_rfid_assign_card(request: HttpRequest) -> JsonResponse:
    """Прив'язує RFID картку до студента."""
    try:
        data = json.loads(request.body)
        uid = data.get("uid", "").strip().upper()
        student_id = data.get("student_id")
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not uid or not student_id:
        return JsonResponse({"error": "uid та student_id обов'язкові"}, status=400)

    student = get_object_or_404(User, pk=student_id, role="student")

    # Перевіряємо чи UID вже не зайнятий іншим студентом
    existing = User.objects.filter(rfid_uid=uid).exclude(pk=student.pk).first()
    if existing:
        return JsonResponse(
            {"error": f"Ця картка вже прив'язана до {existing.full_name}"}, status=409
        )

    student.rfid_uid = uid
    student.save(update_fields=["rfid_uid"])

    # Очищаємо буфер після успішного прив'язування
    _rfid_write_state({"active": False, "uid": None, "scanned_at": None})

    return JsonResponse(
        {
            "ok": True,
            "student": student.full_name,
            "uid": uid,
        }
    )


@role_required("admin")
@require_POST
def api_rfid_unassign_card(request: HttpRequest) -> JsonResponse:
    """Відв'язує RFID картку від студента."""
    try:
        data = json.loads(request.body)
        student_id = data.get("student_id")
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    student = get_object_or_404(User, pk=student_id, role="student")
    student.rfid_uid = None
    student.save(update_fields=["rfid_uid"])
    return JsonResponse({"ok": True, "student": student.full_name})


@login_required
def notifications_page_view(request: HttpRequest) -> HttpResponse:
    """Повна сторінка сповіщень з фільтрами, пагінацією та керуванням."""
    from django.core.paginator import Paginator

    TYPE_FILTER_CHOICES = [
        ("", "Усі"),
        ("grade", "Оцінки"),
        ("absence", "Пропуски"),
        ("homework", "Домашні завдання"),
        ("private_chat", "Приватний чат"),
        ("comment", "Коментарі"),
        ("news", "Новини"),
    ]

    filter_type = request.GET.get("type", "")
    filter_status = request.GET.get("status", "")  # '' | 'unread' | 'read'

    qs = Notification.objects.filter(recipient=request.user)
    if filter_type:
        qs = qs.filter(notif_type=filter_type)
    if filter_status == "unread":
        qs = qs.filter(is_read=False)
    elif filter_status == "read":
        qs = qs.filter(is_read=True)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    # Build link for each notification
    for n in page_obj:
        n.computed_link = _build_notif_link(n)

    unread_total = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()

    context = {
        "page_obj": page_obj,
        "filter_type": filter_type,
        "filter_status": filter_status,
        "type_choices": TYPE_FILTER_CHOICES,
        "unread_total": unread_total,
        "total_count": qs.count(),
        "active_page": "notifications",
    }
    return render(request, "notifications.html", context)


@login_required
def api_student_status(request: HttpRequest) -> JsonResponse:
    """Повертає поточний статус входу для авторизованого студента."""
    student = request.user
    last_access = (
        BuildingAccessLog.objects.filter(student=student).order_by("-timestamp").first()
    )
    in_building = (last_access.action == "ENTER") if last_access else False

    return JsonResponse(
        {
            "in_building": in_building,
            "last_scan": (
                last_access.timestamp.strftime("%H:%M") if last_access else None
            ),
            "has_card": bool(student.rfid_uid),
        }
    )
