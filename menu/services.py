from decimal import Decimal
from menu.models import Product, MenuItemIngredient, DailyMenu

def get_daily_items(date, meal_type):
    dm = DailyMenu.objects.filter(date=date).first()
    if not dm:
        return []
    if meal_type == "breakfast":
        return list(dm.breakfast_items.all())
    if meal_type == "lunch":
        return list(dm.lunch_items.all())
    return []

def deduct_for_items(items):
    item_ids = [i.id for i in items]
    if not item_ids:
        return ["Меню дня пустое"], []

    need = {}
    ings = MenuItemIngredient.objects.select_related("product").filter(item_id__in=item_ids)

    for ing in ings:
        need_amount = Decimal(str(ing.amount))
        pid = ing.product_id
        need[pid] = need.get(pid, Decimal("0")) + need_amount

    products = {p.id: p for p in Product.objects.filter(id__in=need.keys())}

    not_enough = []
    for pid, a in need.items():
        p = products.get(pid)
        if not p:
            continue
        if Decimal(str(p.stock)) < a:
            not_enough.append(f"{p.name}: нужно {a} {p.unit}, есть {p.stock} {p.unit}")

    if not_enough:
        return not_enough, []

    changed = []
    for pid, a in need.items():
        p = products[pid]
        p.stock = Decimal(str(p.stock)) - a
        p.save(update_fields=["stock"])
        changed.append((p.name, a, p.unit))

    return [], changed


def has_recipe(item) -> bool:
    """Есть ли рецепт (ингредиенты связаны с блюдом)"""
    return MenuItemIngredient.objects.filter(item=item).exists()

def has_ingredients(item, portions=1):
    """
    Для витрины/клиента: 'есть ингредиенты' = есть рецепт (связи ингредиентов).
    НЕ проверяем склад, иначе у клиента всё станет 'нет в наличии', пока склад не заполнен.
    """
    return MenuItemIngredient.objects.filter(item=item).exists()