# Generated by Django 5.1.6 on 2025-06-09 11:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0020_remove_exam_generated_topics'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentexamattempt',
            name='feedback',
            field=models.TextField(blank=True, null=True),
        ),
    ]
