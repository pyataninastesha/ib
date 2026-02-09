from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0013_banquetmenu'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='order_type',
            field=models.CharField(
                max_length=20,
                choices=[('regular', 'Обычный'), ('banquet', 'Банкет')],
                default='regular',
                verbose_name='Тип заказа',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='event_date',
            field=models.DateField(blank=True, null=True, verbose_name='Дата мероприятия'),
        ),
        migrations.AddField(
            model_name='order',
            name='guests_count',
            field=models.IntegerField(blank=True, null=True, verbose_name='Количество гостей'),
        ),
    ]
