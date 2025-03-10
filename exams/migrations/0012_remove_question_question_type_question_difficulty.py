# Generated by Django 5.1.3 on 2025-03-10 04:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0011_alter_exam_pdf_document'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='question',
            name='question_type',
        ),
        migrations.AddField(
            model_name='question',
            name='difficulty',
            field=models.CharField(choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')], default='Easy', max_length=10),
            preserve_default=False,
        ),
    ]
