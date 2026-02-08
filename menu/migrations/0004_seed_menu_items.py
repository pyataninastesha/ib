from django.db import migrations


def seed(apps, schema_editor):
    Category = apps.get_model('menu', 'Category')
    MenuItem = apps.get_model('menu', 'MenuItem')

    cat_breakfast, _ = Category.objects.get_or_create(name='Завтраки', defaults={'description': 'Завтраки в школьной столовой', 'order': 1})
    cat_lunch, _ = Category.objects.get_or_create(name='Обеды', defaults={'description': 'Обеды в школьной столовой', 'order': 2})
    cat_drinks, _ = Category.objects.get_or_create(name='Напитки', defaults={'description': 'Напитки', 'order': 3})

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

    upsert(
        'Гречка с курицей в томатном соусе',
        'Состав: гречка, курица, помидоры.',
        140,
        cat_lunch,
        allergens='',
    )
    upsert(
        'Печеный картофель с отварной курицей и горошком',
        'Состав: картошка, курица, горох.',
        150,
        cat_lunch,
        allergens='',
    )
    upsert(
        'Брокколи под ореховым соусом с судаком и морковью',
        'Состав: брокколи, арахис, масло, судак, морковь.',
        190,
        cat_lunch,
        allergens='nuts fish',
    )
    upsert(
        'Куриный суп',
        'Состав: лапша (яйца, мука), картошка, курица, морковь, петрушка, лук, помидоры, лавровый лист.',
        120,
        cat_lunch,
        allergens='gluten eggs',
    )
    upsert(
        'Овощной суп',
        'Состав: морковь, сельдерей, помидоры, цветная капуста, брокколи, горох, картошка.',
        110,
        cat_lunch,
        allergens='',
    )
    upsert(
        'Салат Цезарь',
        'Состав: сухарики, курица, майонез, яйца, листья салата, помидоры, сыр.',
        160,
        cat_lunch,
        allergens='gluten eggs lactose',
    )

    # --- Breakfasts
    upsert(
        'Творожок с клубникой',
        'Состав: творог, клубника, сахар.',
        90,
        cat_breakfast,
        allergens='lactose',
    )
    upsert(
        'Рисовая каша с печеными яблоками',
        'Состав: рис, яблоки.',
        80,
        cat_breakfast,
        allergens='',
    )
    upsert(
        'Рисовая каша на молоке',
        'Состав: рис, молоко.',
        80,
        cat_breakfast,
        allergens='lactose',
    )
    upsert(
        'Омлет с помидорами',
        'Состав: яйца, помидоры, молоко.',
        100,
        cat_breakfast,
        allergens='eggs lactose',
    )
    upsert(
        'Пирожок с яйцом и капустой',
        'Состав: мука, яйца, капуста.',
        60,
        cat_breakfast,
        allergens='gluten eggs',
    )
    upsert(
        'Оладушки',
        'Состав: мука, сахар, молоко, яйца.',
        70,
        cat_breakfast,
        allergens='gluten eggs lactose',
    )
    upsert(
        'Блины с ореховой пастой',
        'Состав: мука, сахар, молоко, яйца, арахис.',
        85,
        cat_breakfast,
        allergens='gluten eggs lactose nuts',
    )
    upsert(
        'Кекс с орехами и клюквой',
        'Состав: мука, сахар, молоко, арахис, клюква, яйца.',
        95,
        cat_breakfast,
        allergens='gluten eggs lactose nuts',
    )

    # --- Drinks
    upsert(
        'Морс',
        'Состав: клюква, сахар.',
        35,
        cat_drinks,
        allergens='',
    )
    upsert(
        'Чай',
        'Состав: чайные листья.',
        20,
        cat_drinks,
        allergens='',
    )
    upsert(
        'Компот',
        'Состав: яблоки, клубника, сахар.',
        30,
        cat_drinks,
        allergens='',
    )
    upsert(
        'Какао',
        'Состав: молоко, какао-порошок, сахар.',
        45,
        cat_drinks,
        allergens='lactose',
    )


def unseed(apps, schema_editor):
    Category = apps.get_model('menu', 'Category')
    MenuItem = apps.get_model('menu', 'MenuItem')
    MenuItem.objects.filter(category__name__in=['Завтраки', 'Обеды', 'Напитки']).delete()
    Category.objects.filter(name__in=['Завтраки', 'Обеды', 'Напитки']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0003_order_received_fields'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
