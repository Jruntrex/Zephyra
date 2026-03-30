"""
Data migration: перехід на 12-бальну систему оцінювання.

1. Видаляє всі записи StudentPerformance
2. Очищує GradingScale і GradeRule
3. Створює нову 12-бальну шкалу з 6 правилами
"""
from django.db import migrations


def switch_to_12_point_scale(apps, schema_editor):
    StudentPerformance = apps.get_model('main', 'StudentPerformance')
    GradingScale = apps.get_model('main', 'GradingScale')
    GradeRule = apps.get_model('main', 'GradeRule')

    # 1. Видалити всі оцінки
    StudentPerformance.objects.all().delete()

    # 2. Очистити старі шкали та правила
    GradeRule.objects.all().delete()
    GradingScale.objects.all().delete()

    # 3. Створити нову 12-бальну шкалу
    scale = GradingScale.objects.create(
        name='12-бальна',
        description='Стандартна 12-бальна шкала оцінювання',
        is_default=True,
        is_active=True,
    )

    rules = [
        {'min_points': 12, 'max_points': 12, 'label': 'Відмінно',     'color': '#16a34a'},
        {'min_points': 10, 'max_points': 11, 'label': 'Дуже добре',   'color': '#2563eb'},
        {'min_points':  7, 'max_points':  9, 'label': 'Добре',        'color': '#0891b2'},
        {'min_points':  4, 'max_points':  6, 'label': 'Задовільно',   'color': '#d97706'},
        {'min_points':  1, 'max_points':  3, 'label': 'Незадовільно', 'color': '#dc2626'},
        {'min_points':  0, 'max_points':  0, 'label': 'Не зараховано','color': '#6b7280'},
    ]

    for r in rules:
        GradeRule.objects.create(scale=scale, **r)


def reverse_switch(apps, schema_editor):
    """Зворотна міграція: видалити 12-бальну шкалу (дані не відновлюються)."""
    GradingScale = apps.get_model('main', 'GradingScale')
    GradingScale.objects.filter(name='12-бальна').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_add_notifications'),
    ]

    operations = [
        migrations.RunPython(switch_to_12_point_scale, reverse_switch),
    ]
