from django.db import migrations


def rename_dz_to_homework(apps, schema_editor):
    db = schema_editor.connection.alias
    EvaluationType = apps.get_model('main', 'EvaluationType')
    EvaluationType.objects.using(db).filter(
        is_homework_type=True,
        name='ДЗ',
    ).update(name='Домашнє Завдання')


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_homework_eval_type'),
    ]

    operations = [
        migrations.RunPython(rename_dz_to_homework, migrations.RunPython.noop),
    ]
