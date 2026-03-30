from django.db import migrations, models


def create_homework_eval_types(apps, schema_editor):
    """Для кожного TeachingAssignment створити ДЗ-тип якщо немає."""
    TeachingAssignment = apps.get_model('main', 'TeachingAssignment')
    EvaluationType = apps.get_model('main', 'EvaluationType')

    for assignment in TeachingAssignment.objects.all():
        exists = EvaluationType.objects.filter(
            assignment=assignment,
            is_homework_type=True
        ).exists()
        if not exists:
            EvaluationType.objects.create(
                assignment=assignment,
                name='Домашнє Завдання',
                weight_percent=30,
                description='Домашнє завдання',
                order=0,
                is_homework_type=True,
                is_active=True,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_google_classroom_ui'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluationtype',
            name='is_homework_type',
            field=models.BooleanField(
                default=False,
                verbose_name='Тип ДЗ',
                help_text='Якщо True — оцінки для цього типу беруться з HomeworkSubmission, а не журналу',
            ),
        ),
        migrations.RunPython(create_homework_eval_types, migrations.RunPython.noop),
    ]
