from django.db import migrations, IntegrityError
import re


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


CANON = {
    # хлеб
    "хлеб тостовый": "Хлеб",

    # салат
    "салат": "Листья салата",
    "салат листовой": "Листья салата",

    # горошек
    "зеленый горошек": "Горошек зелёный",
    "зелёный горошек": "Горошек зелёный",

    # гречка/овсянка/мука
    "гречка": "Гречневая крупа",
    "овсянка": "Овсяные хлопья",
    "мука": "Мука пшеничная",

    # масло
    "масло": "Масло растительное",

    # свекла
    "свекла": "Свёкла",

    # орехи
    "орехи грецкие": "Грецкие орехи",

    # йогурт
    "йогурт": "Йогурт натуральный",

    # вода/бульон
    "водабульон": "Вода",
    "вода/бульон": "Вода",

    # соусы
    "соус цезарь/майонез": "Соус (майонез/цезарь)",
    "соус (майонез/цезарь": "Соус (майонез/цезарь)",
    "соус (майонезцезарь": "Соус (майонез/цезарь)",

    # панировка
    "панировка": "Сухари панировочные",
    "сухарики": "Сухари панировочные",

    # рыба
    "рыба": "Рыба (филе)",
    "рыба (филе": "Рыба (филе)",
    "рыба (филе)": "Рыба (филе)",
    "судак": "Рыба (филе)",
    "судак (филе": "Рыба (филе)",
    "судак (филе)": "Рыба (филе)",
}


def forwards(apps, schema_editor):
    Product = apps.get_model("menu", "Product")
    MenuItemIngredient = apps.get_model("menu", "MenuItemIngredient")

    products = list(Product.objects.all())

    for p in products:
        old_name = (p.name or "").strip()
        key = _norm(old_name)
        canon_name = CANON.get(key)

        if not canon_name or canon_name == old_name:
            continue

        canon_prod = Product.objects.filter(name__iexact=canon_name).first()
        if not canon_prod:
            canon_prod = Product.objects.create(
                name=canon_name,
                unit=p.unit,
                stock=p.stock,
                min_stock=p.min_stock,
            )

        ings = list(MenuItemIngredient.objects.filter(product_id=p.id))
        for ing in ings:
            try:
                ing.product_id = canon_prod.id
                ing.save(update_fields=["product"])
            except IntegrityError:
                exist = MenuItemIngredient.objects.get(item_id=ing.item_id, product_id=canon_prod.id)
                exist.amount = exist.amount + ing.amount
                exist.save(update_fields=["amount"])
                ing.delete()

        if not MenuItemIngredient.objects.filter(product_id=p.id).exists():
            p.delete()


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0011_dailymenu"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
