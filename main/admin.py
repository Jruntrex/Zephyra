from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserAdminForm
from .models import (
    AbsenceReason,
    BuildingAccessLog,
    Classroom,
    EvaluationType,
    GradeRule,
    GradingScale,
    InstitutionSettings,
    Lesson,
    ScheduleTemplate,
    StudentPerformance,
    StudyGroup,
    Subject,
    TeachingAssignment,
    TimeSlot,
    User,
)

# ==========================================
# 1. КОРИСТУВАЧІ
# ==========================================


class UserAdmin(BaseUserAdmin):
    form = UserAdminForm
    add_form = UserAdminForm

    list_display = (
        "email",
        "full_name",
        "role",
        "group",
        "phone",
        "is_active",
        "is_staff",
    )
    list_filter = ("role", "is_staff", "is_active", "group", "created_at")
    search_fields = ("email", "full_name", "phone", "student_id")
    ordering = ("-created_at",)

    fieldsets = (
        ("Основна інформація", {"fields": ("email", "password", "full_name", "role")}),
        (
            "Особисті дані",
            {
                "fields": ("phone", "date_of_birth", "address", "profile_image"),
                "classes": ("collapse",),
            },
        ),
        (
            "Навчальна інформація",
            {
                "fields": ("group", "student_id"),
            },
        ),
        ("Примітки", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Права доступу",
            {
                "fields": ("is_active", "is_staff", "is_superuser"),
            },
        ),
        (
            "Системна інформація",
            {
                "fields": ("created_at", "updated_at", "last_login"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at", "last_login")

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "role",
                    "group",
                    "password",
                    "confirm_password",
                ),
            },
        ),
    )


# ==========================================
# 2. ГРУПИ
# ==========================================


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "specialty",
        "course",
        "year_of_entry",
        "graduation_year",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "course", "year_of_entry")
    search_fields = ("name", "specialty")
    ordering = ("-course", "name")

    fieldsets = (
        ("Основна інформація", {"fields": ("name", "specialty", "course")}),
        ("Навчальний період", {"fields": ("year_of_entry", "graduation_year")}),
        (
            "Системна інформація",
            {
                "fields": ("is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


# ==========================================
# 3. ПРЕДМЕТИ
# ==========================================


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "credits", "semester", "hours_total", "is_active")
    list_filter = ("is_active", "semester", "credits")
    search_fields = ("name", "code", "description")
    ordering = ("semester", "name")

    fieldsets = (
        ("Основна інформація", {"fields": ("name", "code", "description")}),
        (
            "Навчальне навантаження",
            {
                "fields": (
                    "credits",
                    "semester",
                    "hours_total",
                    "hours_lectures",
                    "hours_practicals",
                )
            },
        ),
        (
            "Системна інформація",
            {
                "fields": ("is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


# ==========================================
# 4. АУДИТОРІЇ
# ==========================================


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("name", "building", "floor", "type", "capacity", "is_active")
    list_filter = ("is_active", "type", "building", "floor")
    search_fields = ("name", "building", "equipment")
    ordering = ("building", "floor", "name")

    fieldsets = (
        (
            "Основна інформація",
            {"fields": ("name", "building", "floor", "type", "capacity")},
        ),
        ("Обладнання", {"fields": ("equipment",), "classes": ("collapse",)}),
        (
            "Системна інформація",
            {
                "fields": ("is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


# ==========================================
# 5. ШКАЛИ ОЦІНЮВАННЯ
# ==========================================


class GradeRuleInline(admin.TabularInline):
    model = GradeRule
    extra = 1
    fields = ("label", "min_points", "max_points", "color", "description")


@admin.register(GradingScale)
class GradingScaleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default", "is_active", "created_at")
    list_filter = ("is_default", "is_active")
    search_fields = ("name", "description")
    inlines = [GradeRuleInline]

    fieldsets = (
        ("Основна інформація", {"fields": ("name", "description", "is_default")}),
        (
            "Системна інформація",
            {
                "fields": ("is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


@admin.register(GradeRule)
class GradeRuleAdmin(admin.ModelAdmin):
    list_display = ("scale", "label", "min_points", "max_points", "color")
    list_filter = ("scale",)
    search_fields = ("label", "description")
    ordering = ("scale", "-min_points")

    fieldsets = (
        ("Основна інформація", {"fields": ("scale", "label")}),
        ("Бали", {"fields": ("min_points", "max_points")}),
        ("Відображення", {"fields": ("color", "description")}),
        (
            "Системна інформація",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ("created_at", "updated_at")


# ==========================================
# 6. НАВАНТАЖЕННЯ ВИКЛАДАЧІВ
# ==========================================


class EvaluationTypeInline(admin.TabularInline):
    model = EvaluationType
    extra = 1
    fields = ("name", "weight_percent", "order", "is_active")


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "teacher",
        "group",
        "academic_year",
        "semester",
        "is_active",
    )
    list_filter = ("is_active", "semester", "academic_year", "subject", "group")
    search_fields = ("subject__name", "teacher__full_name", "group__name")
    ordering = ("-academic_year", "subject")
    inlines = [EvaluationTypeInline]

    fieldsets = (
        ("Основна інформація", {"fields": ("subject", "teacher", "group")}),
        (
            "Навчальний період",
            {"fields": ("academic_year", "semester", "start_date", "end_date")},
        ),
        ("Примітки", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Системна інформація",
            {
                "fields": ("is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


@admin.register(EvaluationType)
class EvaluationTypeAdmin(admin.ModelAdmin):
    list_display = ("assignment", "name", "weight_percent", "order", "is_active")
    list_filter = ("is_active", "assignment__subject")
    search_fields = ("name", "description")
    ordering = ("assignment", "order")

    fieldsets = (
        ("Основна інформація", {"fields": ("assignment", "name", "weight_percent")}),
        ("Додаткова інформація", {"fields": ("description", "order")}),
        (
            "Системна інформація",
            {
                "fields": ("is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


# ==========================================
# 7. РОЗКЛАД ДЗВІНКІВ
# ==========================================


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("lesson_number", "name", "start_time", "end_time", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("lesson_number",)

    fieldsets = (
        (
            "Основна інформація",
            {"fields": ("lesson_number", "name", "start_time", "end_time")},
        ),
        (
            "Системна інформація",
            {
                "fields": ("is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


# ==========================================
# 8. ШАБЛОНИ РОЗКЛАДУ
# ==========================================


@admin.register(ScheduleTemplate)
class ScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "get_group",
        "get_day",
        "lesson_number",
        "get_subject",
        "get_teacher",
        "start_time",
        "classroom",
        "is_active",
    )
    list_filter = (
        "is_active",
        "group",
        "day_of_week",
        "subject",
        "teacher",
        "week_type",
    )
    search_fields = ("group__name", "subject__name", "teacher__full_name", "notes")
    ordering = ("group", "day_of_week", "lesson_number")

    fieldsets = (
        ("Основна інформація", {"fields": ("group", "day_of_week", "lesson_number")}),
        (
            "Предмет та викладач",
            {"fields": ("subject", "teacher", "teaching_assignment")},
        ),
        (
            "Розклад",
            {"fields": ("start_time", "duration_minutes", "classroom", "week_type")},
        ),
        ("Дійсність", {"fields": ("valid_from", "valid_to")}),
        ("Примітки", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Системна інформація",
            {
                "fields": ("is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("valid_from", "created_at", "updated_at")

    def get_group(self, obj):
        return obj.group.name

    get_group.short_description = "Група"

    def get_day(self, obj):
        return obj.get_day_of_week_display()

    get_day.short_description = "День"

    def get_subject(self, obj):
        return obj.subject.name

    get_subject.short_description = "Предмет"

    def get_teacher(self, obj):
        return obj.teacher.full_name if obj.teacher else "—"

    get_teacher.short_description = "Викладач"

    def save_model(self, request, obj, form, change):
        if obj.teacher and obj.subject and obj.group:
            obj.teaching_assignment, _ = TeachingAssignment.objects.get_or_create(
                subject=obj.subject, teacher=obj.teacher, group=obj.group
            )
        super().save_model(request, obj, form, change)


# ==========================================
# 9. УРОКИ
# ==========================================


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "start_time",
        "get_subject",
        "get_group",
        "get_teacher",
        "topic",
        "is_cancelled",
    )
    list_filter = (
        "is_cancelled",
        "date",
        "group",
        "subject",
        "teacher",
        "evaluation_type",
    )
    search_fields = (
        "topic",
        "notes",
        "homework",
        "group__name",
        "subject__name",
        "teacher__full_name",
    )
    ordering = ("-date", "start_time")
    date_hierarchy = "date"

    fieldsets = (
        (
            "Основна інформація",
            {"fields": ("group", "subject", "teacher", "evaluation_type")},
        ),
        ("Розклад", {"fields": ("date", "start_time", "end_time", "classroom")}),
        ("Зміст заняття", {"fields": ("topic", "max_points", "homework", "materials")}),
        ("Статус", {"fields": ("is_cancelled", "cancellation_reason")}),
        ("Примітки", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Системна інформація",
            {
                "fields": ("template_source", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")

    def get_subject(self, obj):
        return obj.subject.name

    get_subject.short_description = "Предмет"

    def get_group(self, obj):
        return obj.group.name

    get_group.short_description = "Група"

    def get_teacher(self, obj):
        return obj.teacher.full_name

    get_teacher.short_description = "Викладач"


# ==========================================
# 10. УСПІШНІСТЬ СТУДЕНТІВ
# ==========================================


@admin.register(StudentPerformance)
class StudentPerformanceAdmin(admin.ModelAdmin):
    list_display = (
        "get_student",
        "get_lesson",
        "earned_points",
        "absence",
        "is_bonus",
        "graded_at",
    )
    list_filter = (
        "is_bonus",
        "absence",
        "graded_at",
        "lesson__date",
        "lesson__subject",
        "student__group",
    )
    search_fields = ("student__full_name", "comment", "lesson__topic")
    ordering = ("-lesson__date", "student__full_name")
    date_hierarchy = "lesson__date"

    fieldsets = (
        ("Основна інформація", {"fields": ("lesson", "student")}),
        ("Оцінювання", {"fields": ("earned_points", "absence", "is_bonus")}),
        ("Коментар", {"fields": ("comment",)}),
        (
            "Системна інформація",
            {
                "fields": (
                    "graded_by",
                    "graded_at",
                    "version",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")

    def get_student(self, obj):
        return obj.student.full_name

    get_student.short_description = "Студент"

    def get_lesson(self, obj):
        return f"{obj.lesson.date} - {obj.lesson.subject.name}"

    get_lesson.short_description = "Урок"


# ==========================================
# 11. ПРИЧИНИ ПРОПУСКІВ
# ==========================================


@admin.register(AbsenceReason)
class AbsenceReasonAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "description",
        "is_respectful",
        "order",
        "color",
        "is_active",
    )
    list_filter = ("is_respectful", "is_active")
    search_fields = ("code", "description")
    ordering = ("order", "code")

    fieldsets = (
        ("Основна інформація", {"fields": ("code", "description", "is_respectful")}),
        ("Відображення", {"fields": ("order", "color")}),
        (
            "Системна інформація",
            {
                "fields": ("is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


# ==========================================
# 12. ЛОГИ ДОСТУПУ
# ==========================================


@admin.register(BuildingAccessLog)
class BuildingAccessLogAdmin(admin.ModelAdmin):
    list_display = (
        "get_student",
        "timestamp",
        "action",
        "location",
        "device_id",
        "is_valid",
    )
    list_filter = ("action", "is_valid", "location", "timestamp")
    search_fields = ("student__full_name", "location", "device_id", "notes")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"

    fieldsets = (
        ("Основна інформація", {"fields": ("student", "timestamp", "action")}),
        ("Деталі доступу", {"fields": ("location", "device_id", "is_valid")}),
        ("Примітки", {"fields": ("notes",), "classes": ("collapse",)}),
    )

    readonly_fields = ("timestamp",)

    def get_student(self, obj):
        return obj.student.full_name

    get_student.short_description = "Студент"


# Реєструємо User окремо
admin.site.register(User, UserAdmin)


# ==========================================
# НАЛАШТУВАННЯ ЗАКЛАДУ (SINGLETON)
# ==========================================


@admin.register(InstitutionSettings)
class InstitutionSettingsAdmin(admin.ModelAdmin):
    """
    Singleton admin: prevents creating a second record.
    'Add' button is hidden when a record already exists.
    """

    fieldsets = (
        ("Ідентифікація закладу", {"fields": ("name", "tagline")}),
        ("Медіафайли", {"fields": ("logo", "favicon")}),
        ("Системна інформація", {"fields": ("updated_at",), "classes": ("collapse",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not InstitutionSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
