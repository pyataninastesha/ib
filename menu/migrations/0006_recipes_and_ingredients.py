from django.db import migrations

RECIPES = {
    "Блины с ореховой пастой": {
        "recipe": "1) Замесить тесто (молоко, яйцо, мука, сахар, соль).\n2) Жарить блины на сковороде.\n3) Смазать ореховой пастой, свернуть/подать.",
        "ings": [
            ("Мука пшеничная", "г", 60),
            ("Молоко", "мл", 120),
            ("Яйцо", "шт", 1),
            ("Сахар", "г", 10),
            ("Соль", "г", 1),
            ("Масло растительное", "мл", 5),
            ("Ореховая паста", "г", 30),
        ]
    },
    "Блины с шоколадом": {
        "recipe": "1) Замесить тесто.\n2) Жарить блины.\n3) Начинить шоколадом/пастой, подать горячими.",
        "ings": [
            ("Мука пшеничная", "г", 60),
            ("Молоко", "мл", 120),
            ("Яйцо", "шт", 1),
            ("Сахар", "г", 10),
            ("Соль", "г", 1),
            ("Масло растительное", "мл", 5),
            ("Шоколад", "г", 25),
        ]
    },
    "Булочка с кунжутом": {
        "recipe": "1) Замесить дрожжевое тесто.\n2) Сформировать булочку.\n3) Смазать яйцом, посыпать кунжутом.\n4) Выпекать 15–20 мин при 180°C.",
        "ings": [
            ("Мука пшеничная", "г", 90),
            ("Молоко", "мл", 50),
            ("Дрожжи", "г", 3),
            ("Сахар", "г", 8),
            ("Соль", "г", 1),
            ("Масло сливочное", "г", 10),
            ("Кунжут", "г", 5),
            ("Яйцо", "шт", 0.2),
        ]
    },
    "Каша манная на молоке": {
        "recipe": "1) Довести молоко до кипения.\n2) Тонкой струйкой всыпать манку, постоянно помешивая.\n3) Варить 3–5 мин, добавить сахар и масло.",
        "ings": [
            ("Молоко", "мл", 250),
            ("Крупа манная", "г", 30),
            ("Сахар", "г", 10),
            ("Соль", "г", 1),
            ("Масло сливочное", "г", 5),
        ]
    },
    "Круассан с шоколадом": {
        "recipe": "1) Тесто слоёное раскатать.\n2) Выложить шоколад, свернуть круассан.\n3) Смазать яйцом.\n4) Выпекать 18–20 мин при 190°C.",
        "ings": [
            ("Тесто слоёное", "г", 90),
            ("Шоколад", "г", 25),
            ("Яйцо", "шт", 0.2),
        ]
    },
}

def seed(apps, schema_editor):
    MenuItem = apps.get_model("menu", "MenuItem")
    Product = apps.get_model("menu", "Product")
    MenuItemIngredient = apps.get_model("menu", "MenuItemIngredient")

    for item_name, data in RECIPES.items():
        try:
            item = MenuItem.objects.get(name=item_name)
        except MenuItem.DoesNotExist:
            continue

        # рецепт -> description
        item.description = data["recipe"]
        item.save(update_fields=["description"])

        # ингредиенты
        for prod_name, unit, amount in data["ings"]:
            prod, _ = Product.objects.get_or_create(name=prod_name, defaults={"unit": unit, "stock": 0, "min_stock": 0})
            if prod.unit != unit:
                prod.unit = unit
                prod.save(update_fields=["unit"])

            MenuItemIngredient.objects.get_or_create(item=item, product=prod, defaults={"amount": amount})

class Migration(migrations.Migration):
    # Эта миграция использует модель Product (apps.get_model('menu','Product')).
    # Product создаётся в параллельной миграции 0006_product_alter_menuitem_allergens_menuitemingredient.
    # Поэтому здесь зависим от неё, иначе на чистой БД миграция упадёт с LookupError.
    dependencies = [
        ("menu", "0006_product_alter_menuitem_allergens_menuitemingredient"),
    ]

    operations = [
        migrations.RunPython(seed),
    ]
