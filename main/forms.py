# main/forms.py

from typing import Any, Dict, List, Optional

from django import forms
from django.core.exceptions import ValidationError
from django.forms import ModelForm

from .models import (
    Classroom,
    EvaluationType,
    Lesson,
    StudyGroup,
    Subject,
    TeachingAssignment,
    User,
)


class UserAdminForm(forms.ModelForm):
    """Кастомна форма для моделі User з коректним хешуванням пароля та підтвердженням."""

    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput,
        required=False,
        help_text="Залиште пустим, щоб не змінювати пароль",
    )

    confirm_password = forms.CharField(
        label="Підтвердіть пароль",
        widget=forms.PasswordInput,
        required=False,
    )

    # Додаємо поле для вибору предметів (для викладачів)
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Предмети (для викладачів)",
    )

    class Meta:
        model = User
        fields = ["full_name", "email", "role", "password", "group"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Якщо редагуємо користувача (instance), то завантажуємо його предмети
        if self.instance.pk:
            # Редагування існуючого користувача - пароль опціональний
            self.fields["password"].required = False
            self.fields["confirm_password"].required = False
            if self.instance.role == "teacher":
                # Отримуємо предмети, які викладає цей викладач
                teacher_subjects = Subject.objects.filter(
                    teachingassignment__teacher=self.instance
                ).distinct()
                self.fields["subjects"].initial = teacher_subjects
        else:
            # Створення нового користувача - пароль обов'язковий
            self.fields["password"].required = True
            self.fields["confirm_password"].required = True

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password or confirm_password:
            if password != confirm_password:
                raise ValidationError("Паролі не співпадають")
        return cleaned_data

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)

        # Хешування нового пароля, якщо він був наданий
        new_password = self.cleaned_data.get("password")
        if new_password:
            user.set_password(new_password)

        # Забезпечення, що group = NULL для не-студентів
        if user.role != "student":
            user.group = None

        if commit:
            user.save()

            # Обробляємо предмети тільки для викладачів
            if user.role == "teacher":
                selected_subjects = self.cleaned_data.get("subjects", [])

                # Отримуємо поточні призначення
                current_assignments = TeachingAssignment.objects.filter(teacher=user)

                # Створюємо множину пар (subject_id, group_id) для вибраних предметів
                desired_assignments = set()
                for subject in selected_subjects:
                    for group in StudyGroup.objects.all():
                        desired_assignments.add((subject.id, group.id))

                # Знаходимо призначення які треба видалити (тільки ті, що не мають Lesson)
                for assignment in current_assignments:
                    pair = (assignment.subject_id, assignment.group_id)
                    if pair not in desired_assignments:
                        # Перевіряємо чи є пов'язані заняття в новій системі
                        if not Lesson.objects.filter(
                            teacher=user,
                            subject=assignment.subject,
                            group=assignment.group,
                        ).exists():
                            assignment.delete()

                # Додаємо нові призначення (якщо вони ще не існують)
                existing_pairs = set(
                    current_assignments.values_list("subject_id", "group_id")
                )
                for subject in selected_subjects:
                    for group in StudyGroup.objects.all():
                        pair = (subject.id, group.id)
                        if pair not in existing_pairs:
                            TeachingAssignment.objects.create(
                                subject=subject,
                                teacher=user,
                                group=group,
                            )

        return user


class StudyGroupForm(ModelForm):
    """Проста форма для додавання/редагування навчальної групи."""

    class Meta:
        model = StudyGroup
        fields = ["name"]


class SubjectForm(ModelForm):
    """Форма для додавання/редагування предмета."""

    class Meta:
        model = Subject
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Назва предмета"}),
        }


class ClassroomForm(ModelForm):
    """Форма для додавання/редагування аудиторії."""

    class Meta:
        model = Classroom
        fields = ["name", "building", "capacity"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Номер/Назва"}),
            "building": forms.TextInput(attrs={"placeholder": "Корпус"}),
            "capacity": forms.NumberInput(attrs={"placeholder": "Місткість"}),
        }


# ==========================================
# API VALIDATION FORMS
# ==========================================


class JournalEntryForm(forms.Form):
    """Валідація одного запису журналу."""

    student_pk = forms.IntegerField(label="ID студента")
    date = forms.DateField(input_formats=["%Y-%m-%d"], label="Дата")
    lesson_num = forms.IntegerField(min_value=1, max_value=8, label="Номер пари")
    subject_id = forms.IntegerField(label="ID предмету")
    value = forms.CharField(required=False, label="Значення")

    def clean_value(self) -> Optional[str]:
        val = self.cleaned_data.get("value")
        if val in [None, "", "—"]:
            return None
        # Перевірка числових оцінок
        if val is not None and str(val).lstrip("-").isdigit():
            num = int(val)
            if not (1 <= num <= 12):
                raise forms.ValidationError("Оцінка має бути від 1 до 12")
        return val


class ScheduleSlotForm(forms.Form):
    """Валідація слоту розкладу (API)."""

    group_id = forms.IntegerField()
    day = forms.IntegerField(min_value=1, max_value=5)
    lesson_number = forms.IntegerField(min_value=1, max_value=7)
    subject_id = forms.IntegerField(required=False)  # Може бути None для видалення
    teacher_id = forms.IntegerField(required=False)
    classroom_id = forms.IntegerField(required=False)
    start_time = forms.TimeField(input_formats=["%H:%M"])
    duration = forms.IntegerField(min_value=1, initial=50)


class EvaluationTypeForm(ModelForm):
    """Форма для додавання типу оцінювання."""

    class Meta:
        model = EvaluationType
        fields = ["name", "weight_percent", "description", "order"]
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "Наприклад: Лекція, Практика..."}
            ),
            "weight_percent": forms.NumberInput(
                attrs={"placeholder": "0", "min": "0", "max": "100", "step": "0.01"}
            ),
            "description": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Опис (необов'язково)"}
            ),
            "order": forms.NumberInput(attrs={"min": "0"}),
        }


class ProfileForm(forms.ModelForm):
    """Форма для самостійного редагування профілю користувачем."""

    class Meta:
        model = User
        fields = ["full_name", "phone", "address", "date_of_birth", "profile_image"]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Email не можна змінювати самостійно (зазвичай це логін)
        # Якщо треба змінити - звертайтесь до адміна
