from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0010_rename_dz_to_homework'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='link',
            field=models.CharField(blank=True, max_length=500, verbose_name='Посилання'),
        ),
        migrations.AddField(
            model_name='notification',
            name='lesson',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='notifications',
                to='main.lesson',
                verbose_name='Урок',
            ),
        ),
        migrations.AlterField(
            model_name='notification',
            name='notif_type',
            field=models.CharField(
                choices=[
                    ('news',         'Новини'),
                    ('comment',      'Коментар'),
                    ('grade',        'Оцінка'),
                    ('absence',      'Пропуск'),
                    ('homework',     'Домашнє завдання'),
                    ('private_chat', 'Приватний чат'),
                ],
                max_length=20,
                verbose_name='Тип',
            ),
        ),
    ]
