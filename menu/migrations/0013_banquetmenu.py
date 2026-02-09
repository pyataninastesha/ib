from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0012_normalize_products_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BanquetMenu',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активно')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name': 'Меню для банкета',
                'verbose_name_plural': 'Меню для банкетов',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddField(
            model_name='banquetmenu',
            name='items',
            field=models.ManyToManyField(blank=True, related_name='banquet_menus', to='menu.menuitem', verbose_name='Блюда'),
        ),
    ]
