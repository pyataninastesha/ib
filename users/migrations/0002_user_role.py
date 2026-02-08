from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[('student', 'Ученик'), ('cook', 'Повар'), ('admin', 'Администратор')],
                default='student',
                max_length=20,
                verbose_name='Роль',
            ),
        ),
    ]
