from django.db import migrations

def add_items(apps, schema_editor):
    Category = apps.get_model('menu', 'Category')
    MenuItem = apps.get_model('menu', 'MenuItem')

    cat_breakfast = Category.objects.get(name='Завтраки')
    cat_lunch = Category.objects.get(name='Обеды')
    cat_drinks = Category.objects.get(name='Напитки')

    def upsert(name, description, price, category, allergens=''):
        MenuItem.objects.update_or_create(
            name=name,
            defaults={
                'description': description,
                'price': price,
                'category': category,
                'allergens': allergens,
                'is_available': True,
            }
        )

    upsert('Йогурт с клубникой', 'Состав: йогурт, клубника, сахар.', 85, cat_breakfast, 'lactose strawberry')
    upsert('Сырники', 'Состав: творог, яйца, мука, сахар.', 95, cat_breakfast, 'lactose eggs gluten')
    upsert('Паста с сыром', 'Состав: макароны, сыр, масло.', 140, cat_lunch, 'gluten lactose')
    upsert('Рыбные котлеты с пюре', 'Состав: рыба, картофель, молоко, масло.', 170, cat_lunch, 'fish lactose')
    upsert('Шоколадный напиток', 'Состав: молоко, какао, сахар.', 50, cat_drinks, 'lactose cocoa')

def remove_items(apps, schema_editor):
    MenuItem = apps.get_model('menu', 'MenuItem')
    names = [
        'Йогурт с клубникой',
        'Сырники',
        'Паста с сыром',
        'Рыбные котлеты с пюре',
        'Шоколадный напиток',
    ]
    MenuItem.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0004_seed_menu_items'),
    ]

    operations = [
        migrations.RunPython(add_items, remove_items),
    ]
