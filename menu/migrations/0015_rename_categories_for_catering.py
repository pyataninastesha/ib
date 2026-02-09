from django.db import migrations


def rename_categories(apps, schema_editor):
    Category = apps.get_model('menu', 'Category')

    # Переименовываем категории из школьной «столовой» в кейтеринг.
    Category.objects.filter(name='Завтраки').update(
        name='Закуски',
        description='Закуски для кейтеринга',
        order=1,
    )
    Category.objects.filter(name='Обеды').update(
        name='Основные блюда',
        description='Основные блюда для кейтеринга',
        order=2,
    )


def reverse_rename(apps, schema_editor):
    Category = apps.get_model('menu', 'Category')
    Category.objects.filter(name='Закуски').update(
        name='Завтраки',
        description='Завтраки в школьной столовой',
        order=1,
    )
    Category.objects.filter(name='Основные блюда').update(
        name='Обеды',
        description='Обеды в школьной столовой',
        order=2,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('menu', '0014_order_banquet_fields'),
    ]

    operations = [
        migrations.RunPython(rename_categories, reverse_rename),
    ]
