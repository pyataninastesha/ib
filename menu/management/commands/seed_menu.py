import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from menu.models import Category, MenuItem, Product, MenuItemIngredient


class Command(BaseCommand):
    help = "Seed menu from data/menu_seed.json (with ingredients)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Clear menu before seeding")

    @transaction.atomic
    def handle(self, *args, **options):
        data_path = Path(__file__).resolve().parents[3] / "data" / "menu_seed.json"
        if not data_path.exists():
            raise CommandError(f"Seed file not found: {data_path}")

        data = json.loads(data_path.read_text(encoding="utf-8"))

        if options["reset"]:
            MenuItemIngredient.objects.all().delete()
            MenuItem.objects.all().delete()
            Category.objects.all().delete()
            # продукты не трогаем (вдруг склад ведёшь)

        for category_name, items in data.items():
            category, _ = Category.objects.get_or_create(name=category_name)

            for item_data in items:
                name = (item_data.get("name") or "").strip()
                if not name:
                    continue

                item_obj, _ = MenuItem.objects.get_or_create(
                    name=name,
                    category=category,
                    defaults={
                        "price": item_data.get("price", 0),
                        "description": item_data.get("description", "") or "",
                        "calories": item_data.get("calories", None),
                        "allergens": item_data.get("allergens", "") or "",
                        "is_available": bool(item_data.get("is_available", True)),
                        "is_active": bool(item_data.get("is_active", True)),
                    },
                )

                # если уже был — синхронизируем поля
                item_obj.price = item_data.get("price", item_obj.price)
                item_obj.description = item_data.get("description", item_obj.description) or ""
                item_obj.calories = item_data.get("calories", item_obj.calories)
                item_obj.allergens = item_data.get("allergens", item_obj.allergens) or ""
                item_obj.is_available = bool(item_data.get("is_available", item_obj.is_available))
                if hasattr(item_obj, "is_active"):
                    item_obj.is_active = bool(item_data.get("is_active", getattr(item_obj, "is_active", True)))
                item_obj.save()

                # ----- IMPORTANT PART: ingredients -----
                ingredients = item_data.get("ingredients") or []
                keep_product_names = set()

                for ing in ingredients:
                    product_name = (ing.get("product") or "").strip()
                    if not product_name:
                        continue
                    amount = ing.get("amount", 0)
                    unit = (ing.get("unit") or "г").strip()

                    keep_product_names.add(product_name)

                    product_obj, _ = Product.objects.get_or_create(
                        name=product_name,
                        defaults={"unit": unit, "stock": 0, "min_stock": 0},
                    )

                    # если unit отличается и у продукта пусто/г — обновим
                    if unit and getattr(product_obj, "unit", None) and product_obj.unit != unit and product_obj.unit in ("г", "", None):
                        product_obj.unit = unit
                        product_obj.save(update_fields=["unit"])

                    MenuItemIngredient.objects.update_or_create(
                        item=item_obj,                 # важно: поле обычно item
                        product=product_obj,
                        defaults={"amount": amount},
                    )

                # удалить лишние связи, которых нет в seed
                MenuItemIngredient.objects.filter(item=item_obj).exclude(product__name__in=keep_product_names).delete()

        self.stdout.write(self.style.SUCCESS("seed_menu done"))