# Generated manually for the case project (Django 4.2)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='received_by_student',
            field=models.BooleanField(default=False, verbose_name='Получено учеником'),
        ),
        migrations.AddField(
            model_name='order',
            name='received_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дата получения'),
        ),
    ]
