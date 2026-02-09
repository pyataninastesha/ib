from decimal import Decimal, InvalidOperation
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
    # ВАЖНО: проверяем через related manager, чтобы не было несовпадений по модели/импорту
    return item.ingredients.exists()


def has_ingredients(item, portions=1) -> bool:
    """
    Реальная проверка "в наличии":
    - должен быть рецепт (ингредиенты)
    - по каждому ингредиенту stock >= amount * portions
    """
    qs = item.ingredients.select_related("product").all()
    if not qs.exists():
        return False

    try:
        portions = Decimal(str(portions))
    except (InvalidOperation, TypeError, ValueError):
        portions = Decimal("1")

    for ing in qs:
        try:
            need = Decimal(str(ing.amount)) * portions
        except (InvalidOperation, TypeError, ValueError):
            need = Decimal("0")

        stock = ing.product.stock
        if stock is None:
            stock = Decimal("0")

        try:
            stock = Decimal(str(stock))
        except (InvalidOperation, TypeError, ValueError):
            stock = Decimal("0")

        if stock < need:
            return False

    return True