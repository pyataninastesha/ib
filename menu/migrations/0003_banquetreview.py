from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BanquetReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.IntegerField(choices=[(1, '1 - Ужасно'), (2, '2 - Плохо'), (3, '3 - Нормально'), (4, '4 - Хорошо'), (5, '5 - Отлично')], verbose_name='Оценка')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='banquet_review', to='menu.order', verbose_name='Заказ')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Отзыв на банкет',
                'verbose_name_plural': 'Отзывы на банкеты',
                'ordering': ['-created_at'],
            },
        ),
    ]
