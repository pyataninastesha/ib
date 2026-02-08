from django.db import migrations, models
import uuid
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название')),
                ('org_type', models.CharField(choices=[('school', 'Школа/университет'), ('office', 'Офис/корпоративное питание'), ('cafe', 'Кафе/столовая/ресторан'), ('catering', 'Кейтеринг/мероприятия'), ('retail', 'Магазин/кулинария'), ('ngo', 'НКО/социальная кухня'), ('other', 'Другое')], default='other', max_length=30, verbose_name='Тип заведения')),
                ('goals', models.CharField(blank=True, max_length=250, verbose_name='Цели')),
                ('avg_portions_per_day', models.PositiveIntegerField(default=0, verbose_name='Среднее порций в день')),
                ('join_code', models.CharField(max_length=12, unique=True, verbose_name='Код подключения')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Организация',
                'verbose_name_plural': 'Организации',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='purchaserequest',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='purchase_requests', to='core.organization', verbose_name='Организация'),
        ),
    ]
