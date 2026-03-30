from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0007_lesson_attachments_homework_submissions'),
    ]

    operations = [
        # 1. Add deadline to Lesson
        migrations.AddField(
            model_name='lesson',
            name='deadline',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Термін здачі'),
        ),
        # 2. Add link to LessonAttachment
        migrations.AddField(
            model_name='lessonattachment',
            name='link',
            field=models.URLField(blank=True, verbose_name='Посилання'),
        ),
        # 3. Update HomeworkSubmission: change status choices & default, add grade
        migrations.AlterField(
            model_name='homeworksubmission',
            name='status',
            field=models.CharField(
                choices=[
                    ('assigned', 'Призначено'),
                    ('turned_in', 'Здано'),
                    ('graded', 'Оцінено'),
                    ('missing', 'Пропущено'),
                ],
                default='assigned',
                max_length=20,
                verbose_name='Статус',
            ),
        ),
        migrations.AlterField(
            model_name='homeworksubmission',
            name='attached_file',
            field=models.FileField(blank=True, upload_to='homework_submissions/', verbose_name='Прикріплений файл (застарілий)'),
        ),
        migrations.AddField(
            model_name='homeworksubmission',
            name='grade',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Оцінка'),
        ),
        # 4. Create SubmissionAttachment
        migrations.CreateModel(
            name='SubmissionAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='submission_attachments/', verbose_name='Файл')),
                ('file_name', models.CharField(max_length=255, verbose_name='Назва файлу')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Завантажено')),
                ('submission', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='files',
                    to='main.homeworksubmission',
                    verbose_name='Здача',
                )),
            ],
            options={
                'verbose_name': 'Файл здачі',
                'verbose_name_plural': 'Файли здачі',
                'db_table': 'submission_attachments',
                'ordering': ['uploaded_at'],
            },
        ),
        # 5. Create PrivateComment
        migrations.CreateModel(
            name='PrivateComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(verbose_name='Текст')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Час')),
                ('author', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Автор',
                )),
                ('submission', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='private_comments',
                    to='main.homeworksubmission',
                    verbose_name='Здача',
                )),
            ],
            options={
                'verbose_name': 'Приватний коментар',
                'verbose_name_plural': 'Приватні коментарі',
                'db_table': 'private_comments',
                'ordering': ['created_at'],
            },
        ),
    ]
