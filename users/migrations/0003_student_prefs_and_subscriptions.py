# Generated manually for the case project (Django 4.2)
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def _today():
    return django.utils.timezone.localdate()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avoid_allergens',
            field=models.CharField(blank=True, max_length=200, verbose_name='Исключить аллергены (коды через запятую)'),
        ),
        migrations.AddField(
            model_name='user',
            name='food_preferences',
            field=models.TextField(blank=True, verbose_name='Пищевые предпочтения'),
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan', models.CharField(choices=[('breakfast', 'Завтраки'), ('lunch', 'Обеды')], max_length=20, verbose_name='Тариф')),
                ('period', models.CharField(choices=[('week', '1 неделя'), ('month', '1 месяц')], max_length=20, verbose_name='Период')),
                ('start_date', models.DateField(default=_today, verbose_name='Дата начала')),
                ('end_date', models.DateField(verbose_name='Дата окончания')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to='users.user', verbose_name='Ученик')),
            ],
            options={
                'verbose_name': 'Абонемент',
                'verbose_name_plural': 'Абонементы',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MealReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=_today, verbose_name='Дата')),
                ('meal_type', models.CharField(choices=[('breakfast', 'Завтрак'), ('lunch', 'Обед')], max_length=20, verbose_name='Тип питания')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='users.subscription', verbose_name='Абонемент')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meal_receipts', to='users.user', verbose_name='Ученик')),
            ],
            options={
                'verbose_name': 'Получение питания',
                'verbose_name_plural': 'Получения питания',
                'ordering': ['-date', '-created_at'],
                'unique_together': {('user', 'date', 'meal_type')},
            },
        ),
    ]
