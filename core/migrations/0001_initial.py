from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PurchaseRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Продукт')),
                ('quantity', models.CharField(blank=True, max_length=50, verbose_name='Количество')),
                ('unit', models.CharField(blank=True, max_length=50, verbose_name='Ед. изм.')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('status', models.CharField(choices=[('new', 'Новая'), ('in_progress', 'В работе'), ('done', 'Закуплено')], default='new', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='purchase_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Заявка на закупку',
                'verbose_name_plural': 'Заявки на закупку',
                'ordering': ['-created_at'],
            },
        ),
    ]
