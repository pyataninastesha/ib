from django.db import migrations, IntegrityError
import re


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


# Словарь синонимов
CANON = {
    # помидоры
    "помидор": "Помидоры",
    "помидоры": "Помидоры",
    "томат": "Помидоры",
    "томаты": "Помидоры",

    # яйцо
    "яйцо": "Яйца",
    "яйца": "Яйца",

    # картофель
    "картофель": "Картофель",
    "картошка": "Картофель",

    # лук
    "лук": "Лук репчатый",
    "лук репчатый": "Лук репчатый",

    # морковь
    "морковь": "Морковь",

    # огурцы
    "огурец": "Огурцы",
    "огурцы": "Огурцы",

    # капуста
    "капуста": "Капуста",
    "капуста белокочанная": "Капуста",

    # курица
    "курица": "Курица",
    "куриное филе": "Куриное филе",
    "филе куриное": "Куриное филе",
    "куриный фарш": "Куриный фарш",

    # масло
    "масло сливочное": "Масло сливочное",
    "сливочное масло": "Масло сливочное",
    "масло растительное": "Масло растительное",
    "растительное масло": "Масло растительное",

    # сахар/соль
    "сахар": "Сахар",
    "соль": "Соль",

    # сметана/творог
    "сметана": "Сметана",
    "творог": "Творог",
}

# Для замены слов в "Состав:" (опционально)
REPLACE_IN_TEXT = {
    "помидор": "Помидоры",
    "помидоры": "Помидоры",
    "томат": "Помидоры",
    "томаты": "Помидоры",
    "яйцо": "Яйца",
}


def forwards(apps, schema_editor):
    Product = apps.get_model("menu", "Product")
    MenuItemIngredient = apps.get_model("menu", "MenuItemIngredient")
    MenuItem = apps.get_model("menu", "MenuItem")

    # 1) Слить продукты
    # Собираем список продуктов заранее, чтобы безопасно модифицировать таблицу
    products = list(Product.objects.all())

    for p in products:
        old_name = p.name
        key = _norm(old_name)
        canon_name = CANON.get(key)

        # если продукт не в словаре — пропускаем
        if not canon_name or canon_name == old_name:
            continue

        canon_key = _norm(canon_name)

        # найти/создать канонический продукт
        canon_prod = Product.objects.filter(name__iexact=canon_name).first()
        if not canon_prod:
            canon_prod = Product.objects.create(
                name=canon_name,
                unit=p.unit,
                stock=p.stock,
                min_stock=p.min_stock,
            )

        # 2) Переносим ингредиенты с учётом unique_together(item, product)
        ings = list(MenuItemIngredient.objects.filter(product_id=p.id))
        for ing in ings:
            try:
                ing.product_id = canon_prod.id
                ing.save(update_fields=["product"])
            except IntegrityError:
                # значит уже есть (item, canon_prod) — суммируем
                exist = MenuItemIngredient.objects.get(item_id=ing.item_id, product_id=canon_prod.id)
                exist.amount = exist.amount + ing.amount
                exist.save(update_fields=["amount"])
                ing.delete()

        # 3) удалить старый продукт, если больше нигде не используется
        if not MenuItemIngredient.objects.filter(product_id=p.id).exists():
            p.delete()

    # 4) (опционально) подчистить текст "Состав:" в описаниях
    # чтобы там тоже были канонические названия
    for item in MenuItem.objects.all():
        desc = item.description or ""
        if "Состав:" not in desc:
            continue
        new_desc = desc
        for src, dst in REPLACE_IN_TEXT.items():
            # заменяем слова (без учета регистра) приблизительно по границам
            new_desc = re.sub(rf"(?iu)\b{re.escape(src)}\b", dst, new_desc)
        if new_desc != desc:
            item.description = new_desc
            item.save(update_fields=["description"])


def backwards(apps, schema_editor):
    # Откат не делаем (слияние необратимое)
    pass


class Migration(migrations.Migration):
    dependencies = [
        # ВАЖНО: поставь тут свою последнюю миграцию menu:
        # если последняя 0010_dailymenu, то ('menu', '0010_dailymenu')
        ('menu', '0009_real_recipes_for_all_items'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
