from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_switch_to_12_point_scale'),
    ]

    operations = [
        migrations.CreateModel(
            name='LessonAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(blank=True, upload_to='lesson_attachments/', verbose_name='Файл')),
                ('file_name', models.CharField(max_length=255, verbose_name='Назва файлу')),
                ('file_type', models.CharField(
                    choices=[('document', 'Документ'), ('video', 'Відео'), ('link', 'Посилання')],
                    default='document',
                    max_length=20,
                    verbose_name='Тип',
                )),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Завантажено')),
                ('lesson', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments',
                    to='main.lesson',
                    verbose_name='Урок',
                )),
            ],
            options={
                'verbose_name': 'Матеріал уроку',
                'verbose_name_plural': 'Матеріали уроку',
                'db_table': 'lesson_attachments',
                'ordering': ['-uploaded_at'],
            },
        ),
        migrations.CreateModel(
            name='HomeworkSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text_answer', models.TextField(blank=True, verbose_name='Текстова відповідь')),
                ('attached_file', models.FileField(blank=True, upload_to='homework_submissions/', verbose_name='Прикріплений файл')),
                ('status', models.CharField(
                    choices=[('submitted', 'На перевірці'), ('accepted', 'Виконано'), ('returned', 'Повернуто')],
                    default='submitted',
                    max_length=20,
                    verbose_name='Статус',
                )),
                ('submitted_at', models.DateTimeField(auto_now_add=True, verbose_name='Здано')),
                ('lesson', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='submissions',
                    to='main.lesson',
                    verbose_name='Урок',
                )),
                ('student', models.ForeignKey(
                    limit_choices_to={'role': 'student'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='homework_submissions',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Студент',
                )),
            ],
            options={
                'verbose_name': 'Здача ДЗ',
                'verbose_name_plural': 'Здачі ДЗ',
                'db_table': 'homework_submissions',
                'ordering': ['-submitted_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='homeworksubmission',
            constraint=models.UniqueConstraint(fields=('lesson', 'student'), name='unique_homework_submission'),
        ),
    ]
