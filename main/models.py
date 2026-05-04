from typing import Any, List, Optional, Union

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# ==========================================
# 1. БАЗОВІ СУТНОСТІ (АДМІНІСТРАТИВНІ)
# ==========================================


class Specialty(models.Model):
    """Спеціальність (напр. 121 - Інженерія програмного забезпечення)"""

    name = models.CharField(
        max_length=200, unique=True, verbose_name="Назва спеціальності"
    )
    code = models.CharField(max_length=20, blank=True, verbose_name="Код спеціальності")
    description = models.TextField(blank=True, verbose_name="Опис")

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "specialties"
        verbose_name = "Спеціальність"
        verbose_name_plural = "Спеціальності"
        ordering = ["code", "name"]

    def __str__(self) -> str:
        if self.code:
            return f"{self.code} — {self.name}"
        return self.name


class StudyGroup(models.Model):
    """Група студентів (напр. КН-41)"""

    name = models.CharField(max_length=50, unique=True, verbose_name="Назва групи")

    # Додаткові поля
    year_of_entry = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Рік вступу"
    )
    graduation_year = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Рік випуску"
    )
    specialty = models.ForeignKey(
        "Specialty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="groups",
        verbose_name="Спеціальність",
    )
    course = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(6)],
        verbose_name="Курс",
        db_index=True,
    )

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "study_groups"
        verbose_name = "Група"
        verbose_name_plural = "Групи"

    def __str__(self) -> str:
        return self.name


class CustomUserManager(BaseUserManager):
    """Менеджер для створення користувачів (потрібен для AbstractBaseUser)"""

    def create_user(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> "User":
        if not email:
            raise ValueError("Email є обов'язковим")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")  # Адмін за замовчуванням
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Оновлена модель користувача з повною інтеграцією Django Auth"""

    ROLE_CHOICES = [
        ("admin", "Адміністратор"),
        ("teacher", "Викладач"),
        ("student", "Студент"),
    ]

    email = models.EmailField(unique=True, verbose_name="Email")
    full_name = models.CharField(max_length=255, verbose_name="ПІБ")
    role = models.CharField(
        max_length=10, choices=ROLE_CHOICES, default="student", verbose_name="Роль"
    )

    # Студент прив'язаний до групи, викладачі/адміни - ні
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )

    # Додаткова інформація
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    date_of_birth = models.DateField(
        null=True, blank=True, verbose_name="Дата народження"
    )
    address = models.TextField(blank=True, verbose_name="Адреса")
    profile_image = models.ImageField(
        upload_to="profiles/", null=True, blank=True, verbose_name="Фото профілю"
    )
    student_id = models.CharField(
        max_length=50, blank=True, verbose_name="№ студентського квитка"
    )
    rfid_uid = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        verbose_name="RFID UID картки",
    )
    notes = models.TextField(blank=True, verbose_name="Примітки")

    # Налаштування інтерфейсу
    THEME_CHOICES = [("light", "Світла"), ("dark", "Темна")]
    theme = models.CharField(
        max_length=5,
        choices=THEME_CHOICES,
        default="light",
        verbose_name="Тема інтерфейсу",
    )

    # Технічні поля Django
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Чи має доступ до адмінки
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    objects = CustomUserManager()

    USERNAME_FIELD = "email"  # Логін через Email
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "tbl_users"
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"

    def __str__(self) -> str:
        return f"{self.full_name} ({self.get_role_display()})"


class Subject(models.Model):
    """
    Довідник предметів.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Назва предмету")
    code = models.CharField(max_length=20, blank=True, verbose_name="Код предмету")
    description = models.TextField(blank=True, verbose_name="Опис")

    # Навчальна інформація
    credits = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Кредити ECTS"
    )
    hours_total = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Всього годин"
    )
    hours_lectures = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Годин лекцій"
    )
    hours_practicals = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Годин практичних"
    )
    semester = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        verbose_name="Семестр",
    )

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активний")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "subjects"
        verbose_name = "Предмет"
        verbose_name_plural = "Предмети"

    def __str__(self) -> str:
        return self.name


class Classroom(models.Model):
    """Аудиторія (напр. 305-А)"""

    CLASSROOM_TYPE_CHOICES = [
        ("lecture", "Лекційна"),
        ("computer", "Комп'ютерна"),
        ("lab", "Лабораторна"),
        ("other", "Інша"),
    ]

    name = models.CharField(max_length=50, unique=True, verbose_name="Назва/Номер")
    building = models.CharField(max_length=100, blank=True, verbose_name="Корпус")
    floor = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Поверх"
    )
    capacity = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Місткість"
    )
    type = models.CharField(
        max_length=20,
        choices=CLASSROOM_TYPE_CHOICES,
        default="other",
        verbose_name="Тип",
    )
    equipment = models.TextField(blank=True, verbose_name="Обладнання")

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "classrooms"
        verbose_name = "Аудиторія"
        verbose_name_plural = "Аудиторії"

    def __str__(self) -> str:
        return f"{self.name} ({self.building})" if self.building else self.name


class GradingScale(models.Model):
    """Шкала оцінювання (напр. 100-бальна, ЄКТС)"""

    name = models.CharField(max_length=50, unique=True, verbose_name="Назва шкали")
    description = models.TextField(blank=True, verbose_name="Опис")
    is_default = models.BooleanField(default=False, verbose_name="За замовчуванням")

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "grading_scales"
        verbose_name = "Шкала оцінювання"
        verbose_name_plural = "Шкали оцінювання"

    def __str__(self) -> str:
        return self.name


class GradeRule(models.Model):
    """Правила переведення балів у оцінки (напр. 90+ = Відмінно)"""

    scale = models.ForeignKey(
        GradingScale, on_delete=models.CASCADE, related_name="rules"
    )
    label = models.CharField(max_length=50, verbose_name="Оцінка (словом/буквою)")
    min_points = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="Мінімальний бал"
    )
    max_points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Максимальний бал",
    )
    color = models.CharField(max_length=7, blank=True, verbose_name="Колір (hex)")
    description = models.TextField(blank=True, verbose_name="Опис критеріїв")

    # Технічні поля
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "grade_rules"
        ordering = ["-min_points"]
        verbose_name = "Правило оцінювання"
        verbose_name_plural = "Правила оцінювання"

    def __str__(self) -> str:
        return f"{self.scale.name}: {self.label} (>= {self.min_points})"


# ==========================================
# 2. НАВЧАЛЬНИЙ ПРОЦЕС (ЗВ'ЯЗКИ)
# ==========================================


class TeachingAssignment(models.Model):
    """
    ПРИЗНАЧЕННЯ: Головна таблиця зв'язку.
    """

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, verbose_name="Предмет"
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "teacher"},
        verbose_name="Викладач",
    )
    group = models.ForeignKey(
        StudyGroup, on_delete=models.CASCADE, verbose_name="Група"
    )

    # Навчальний період
    academic_year = models.CharField(
        max_length=9, blank=True, verbose_name="Навчальний рік"
    )
    semester = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(1, "1 семестр"), (2, "2 семестр")],
        verbose_name="Семестр",
    )
    start_date = models.DateField(null=True, blank=True, verbose_name="Дата початку")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата завершення")
    notes = models.TextField(blank=True, verbose_name="Примітки")

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активне")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "teaching_assignments"
        unique_together = ("subject", "teacher", "group")
        verbose_name = "Навантаження викладача"
        verbose_name_plural = "Навантаження викладачів"

    def __str__(self) -> str:
        return f"{self.subject.name} - {self.group.name} ({self.teacher.full_name})"


class EvaluationType(models.Model):
    """
    КОНФІГУРАЦІЯ ОЦІНЮВАННЯ.
    """

    assignment = models.ForeignKey(
        TeachingAssignment, on_delete=models.CASCADE, related_name="evaluation_types"
    )
    name = models.CharField(max_length=50, verbose_name="Тип заняття (Лекція/Практика)")
    weight_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Вплив на оцінку (%)",
    )
    description = models.TextField(blank=True, verbose_name="Опис")
    order = models.PositiveSmallIntegerField(
        default=0, verbose_name="Порядок відображення"
    )

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активний")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "evaluation_types"
        ordering = ["order"]
        verbose_name = "Тип оцінювання"
        verbose_name_plural = "Типи оцінювання"

    def __str__(self) -> str:
        return f"{self.name} ({self.weight_percent}%)"


class TimeSlot(models.Model):
    """Часові слоти для пар (Дзвінки)"""

    lesson_number = models.PositiveSmallIntegerField(
        unique=True, verbose_name="Номер пари"
    )
    name = models.CharField(max_length=50, blank=True, verbose_name="Назва")
    start_time = models.TimeField(verbose_name="Початок")
    end_time = models.TimeField(verbose_name="Кінець")

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активний")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "time_slots"
        ordering = ["start_time"]
        verbose_name = "Розклад дзвінків"
        verbose_name_plural = "Розклад дзвінків"

    def __str__(self) -> str:
        return f"{self.lesson_number} пара ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"

    def duration_minutes(self) -> int:
        # Допоміжний метод для розрахунку довжини на графіку
        t1 = self.start_time
        t2 = self.end_time
        return (t2.hour * 60 + t2.minute) - (t1.hour * 60 + t1.minute)


# ==========================================
# 3. РОЗКЛАД І ЖУРНАЛ (TIMELORD EDITION)
# ==========================================


class ScheduleTemplate(models.Model):
    """
    Шаблон розкладу (правила).

    MIGRATION NOTE: teaching_assignment - новий зв'язок (від 04.02.2026)
    Старі поля (subject, teacher, group) залишені для міграції.
    """

    # НОВИЙ ЗВ'ЯЗОК: Single Source of Truth
    teaching_assignment = models.ForeignKey(
        TeachingAssignment,
        on_delete=models.CASCADE,
        null=True,  # Тимчасово nullable для міграції
        blank=True,
        related_name="schedule_templates",
        verbose_name="Навантаження викладача",
        help_text="Зв'язок з призначенням викладача (subject+teacher+group)",
    )

    # СТАРІ ПОЛЯ (для зворотної сумісності під час міграції)
    # TODO: Видалити після завершення міграції даних
    group = models.ForeignKey(
        StudyGroup, on_delete=models.CASCADE, verbose_name="Група"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, verbose_name="Предмет"
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "teacher"},
        null=True,
        blank=True,
        verbose_name="Викладач",
    )

    # РОЗКЛАД
    day_of_week = models.IntegerField(
        choices=[
            (1, "Пн"),
            (2, "Вт"),
            (3, "Ср"),
            (4, "Чт"),
            (5, "Пт"),
            (6, "Сб"),
            (7, "Нд"),
        ],
        verbose_name="День тижня",
    )
    lesson_number = models.PositiveSmallIntegerField(
        default=1, verbose_name="Номер пари"
    )
    start_time = models.TimeField(verbose_name="Час початку")
    duration_minutes = models.IntegerField(default=50, verbose_name="Тривалість (хв)")
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Аудиторія",
    )

    valid_from = models.DateField(auto_now_add=True, verbose_name="Діє з")
    valid_to = models.DateField(null=True, blank=True, verbose_name="Діє до")

    # Додаткові поля
    week_type = models.CharField(
        max_length=20,
        blank=True,
        choices=[("numerator", "Чисельник"), ("denominator", "Знаменник")],
        verbose_name="Тип тижня",
    )
    notes = models.TextField(blank=True, verbose_name="Примітки")

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активний")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "schedule_templates"
        verbose_name = "Шаблон розкладу"
        verbose_name_plural = "Шаблони розкладу"
        unique_together = ("group", "day_of_week", "lesson_number")

    def __str__(self) -> str:
        subj = self.subject.name if self.subject else "—"
        grp = self.group.name if self.group else "—"
        return f"{self.get_day_of_week_display()} {self.start_time} - {subj} ({grp})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Переопалювання save для гарантування цілісності та оновлення teaching_assignment."""
        # Автоматично оновлюємо teaching_assignment на основі subject, teacher, group
        if self.teacher and self.subject and self.group:
            self.teaching_assignment, _ = TeachingAssignment.objects.get_or_create(
                subject=self.subject, teacher=self.teacher, group=self.group
            )

        super().save(*args, **kwargs)


class Lesson(models.Model):
    """
    Конкретний урок у календарі.
    """

    group = models.ForeignKey(
        StudyGroup, on_delete=models.CASCADE, verbose_name="Група"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, verbose_name="Предмет"
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "teacher"},
        verbose_name="Викладач",
    )

    date = models.DateField(verbose_name="Дата")
    start_time = models.TimeField(verbose_name="Час початку")
    end_time = models.TimeField(verbose_name="Час закінчення")

    topic = models.CharField(max_length=255, blank=True, verbose_name="Тема заняття")
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Аудиторія",
    )
    max_points = models.PositiveIntegerField(default=12, verbose_name="Макс. балів")
    evaluation_type = models.ForeignKey(
        EvaluationType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Тип заняття",
    )

    template_source = models.ForeignKey(
        ScheduleTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Джерело (шаблон)",
    )

    # Статус
    is_cancelled = models.BooleanField(default=False, verbose_name="Скасований")
    cancellation_reason = models.TextField(
        blank=True, verbose_name="Причина скасування"
    )

    # Технічні поля
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "lessons"
        unique_together = ("group", "date", "start_time")
        ordering = ["-date", "start_time"]
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"

    def __str__(self) -> str:
        return f"{self.date} {self.start_time} - {self.subject.name}"

    @property
    def lesson_number(self) -> int:
        """Повертає номер пари на основі часу початку."""
        from main.constants import DEFAULT_TIME_SLOTS

        for num, (start, _) in DEFAULT_TIME_SLOTS.items():
            if self.start_time == start:
                return num
        return 0


# ==========================================
# 4. УСПІШНІСТЬ СТУДЕНТА
# ==========================================


class AbsenceReason(models.Model):
    """Довідник типів пропусків (Н, Хв, тощо)"""

    code = models.CharField(max_length=5, unique=True)  # Н, Б, В
    description = models.CharField(max_length=100)
    is_respectful = models.BooleanField(default=False, verbose_name="Поважна причина")
    color = models.CharField(max_length=7, blank=True, verbose_name="Колір (hex)")
    order = models.PositiveSmallIntegerField(
        default=0, verbose_name="Порядок відображення"
    )

    # Технічні поля
    is_active = models.BooleanField(default=True, verbose_name="Активний")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "absence_reasons"
        ordering = ["order"]
        verbose_name = "Причина пропуску"
        verbose_name_plural = "Причини пропусків"

    def __str__(self) -> str:
        return self.code


class StudentPerformance(models.Model):
    """
    Єдиний запис про успішність студента на уроці.
    """

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="grades")
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, limit_choices_to={"role": "student"}
    )

    earned_points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Набрані бали",
    )

    absence = models.ForeignKey(
        AbsenceReason,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Пропуск",
    )

    comment = models.TextField(blank=True, verbose_name="Коментар")

    # Додаткові поля
    graded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_performances",
        limit_choices_to={"role__in": ["teacher", "admin"]},
        verbose_name="Оцінено ким",
    )
    graded_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Час виставлення оцінки"
    )
    is_bonus = models.BooleanField(default=False, verbose_name="Бонусні бали")
    version = models.PositiveIntegerField(default=1, verbose_name="Версія запису")

    # Технічні поля
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "student_performance"
        unique_together = ("lesson", "student")
        verbose_name = "Успішність студента"
        verbose_name_plural = "Успішність студентів"

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.lesson.subject.name} ({self.lesson.date})"

    def clean(self) -> None:
        # Валідація: студент має належати до групи, яка вказана в уроці
        if self.student.group != self.lesson.group:
            raise ValidationError(
                "Студент не належить до групи, для якої проводиться урок."
            )


# ==========================================
# 5. СТРІЧКА НОВИН
# ==========================================


class Post(models.Model):
    """Допис у стрічці новин (викладач або адмін)."""

    POST_TYPE_CHOICES = [
        ("general", "Загальні новини"),
        ("group", "Новини групи"),
    ]

    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="posts", verbose_name="Автор"
    )
    post_type = models.CharField(
        max_length=10, choices=POST_TYPE_CHOICES, default="group", verbose_name="Тип"
    )
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="posts",
        verbose_name="Група",
    )
    title = models.CharField(max_length=200, blank=True, verbose_name="Заголовок")
    content = models.TextField(verbose_name="Текст")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "news_posts"
        ordering = ["-created_at"]
        verbose_name = "Допис"
        verbose_name_plural = "Дописи"

    def __str__(self) -> str:
        return f"{self.author.full_name}: {self.content[:50]}"


class Comment(models.Model):
    """Відповідь студента (або будь-кого) під дописом."""

    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="comments", verbose_name="Допис"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="news_comments",
        verbose_name="Автор",
    )
    content = models.TextField(verbose_name="Текст")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "news_comments"
        ordering = ["created_at"]
        verbose_name = "Коментар"
        verbose_name_plural = "Коментарі"

    def __str__(self) -> str:
        return f"{self.author.full_name}: {self.content[:50]}"


class Notification(models.Model):
    """Сповіщення для користувачів."""

    NOTIF_TYPES = [
        ("news", "Новини"),
        ("comment", "Коментар"),
        ("grade", "Оцінка"),
        ("absence", "Пропуск"),
        ("homework", "Домашнє завдання"),
        ("private_chat", "Приватний чат"),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Отримувач",
    )
    notif_type = models.CharField(
        max_length=20, choices=NOTIF_TYPES, verbose_name="Тип"
    )
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    message = models.TextField(blank=True, verbose_name="Текст")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=500, blank=True, verbose_name="Посилання")
    post = models.ForeignKey(
        "Post",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="Допис",
    )
    lesson = models.ForeignKey(
        "Lesson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="Урок",
    )

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        verbose_name = "Сповіщення"
        verbose_name_plural = "Сповіщення"

    def __str__(self) -> str:
        return f"[{self.notif_type}] {self.recipient.full_name}: {self.title}"


class BuildingAccessLog(models.Model):
    """
    Лог доступу до будівлі (Турнікет).
    Фіксує вхід/вихід студентів.
    """

    ACTION_CHOICES = [
        ("ENTER", "Вхід"),
        ("EXIT", "Вихід"),
    ]

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "student"},
        verbose_name="Студент",
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Час події")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name="Дія")

    # Додаткові поля
    location = models.CharField(max_length=100, blank=True, verbose_name="Місце (вхід)")
    device_id = models.CharField(max_length=50, blank=True, verbose_name="ID турнікету")
    is_valid = models.BooleanField(default=True, verbose_name="Валідний доступ")
    notes = models.TextField(blank=True, verbose_name="Примітки")

    class Meta:
        db_table = "building_access_logs"
        ordering = ["-timestamp"]
        verbose_name = "Лог доступу"
        verbose_name_plural = "Логи доступу"

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.get_action_display()} at {self.timestamp}"


class InstitutionSettings(models.Model):
    """Singleton model for institution branding (e.g. MyBosco under Mentorly)."""

    name = models.CharField(
        max_length=200,
        default="MyBosco",
        verbose_name="Назва закладу",
    )
    tagline = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="Слоган",
    )
    logo = models.ImageField(
        upload_to="institution/",
        null=True,
        blank=True,
        verbose_name="Логотип",
    )
    favicon = models.ImageField(
        upload_to="institution/",
        null=True,
        blank=True,
        verbose_name="Фавікон",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "institution_settings"
        verbose_name = "Налаштування закладу"
        verbose_name_plural = "Налаштування закладу"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.pk and InstitutionSettings.objects.exists():
            raise ValidationError("Може існувати лише один запис налаштувань закладу.")
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        return cls.objects.first()
