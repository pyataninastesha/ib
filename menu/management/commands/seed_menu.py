import json
from pathlib import Path
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from menu.models import Category, MenuItem, Product, MenuItemIngredient


class Command(BaseCommand):
    help = "Seed menu from data/menu_seed.json (WITH ingredients)."

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

        total_items = 0
        total_links = 0

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
                        "price": Decimal(str(item_data.get("price", 0))),
                        "description": item_data.get("description", "") or "",
                        "calories": item_data.get("calories", None),
                        "allergens": item_data.get("allergens", "") or "",
                        "is_available": bool(item_data.get("is_available", True)),
                    },
                )

                # обновляем поля (на случай повторного запуска)
                item_obj.price = Decimal(str(item_data.get("price", item_obj.price)))
                item_obj.description = item_data.get("description", item_obj.description) or ""
                item_obj.calories = item_data.get("calories", item_obj.calories)
                item_obj.allergens = item_data.get("allergens", item_obj.allergens) or ""
                item_obj.is_available = bool(item_data.get("is_available", item_obj.is_available))
                item_obj.save()

                total_items += 1

                # берем именно из item_data
                ingredients = item_data.get("ingredients") or []
                keep = set()

                for ing in ingredients:
                    product_name = (ing.get("product") or "").strip()
                    if not product_name:
                        continue
                    unit = (ing.get("unit") or "г").strip()

                    amount = Decimal(str(ing.get("amount", 0)))

                    keep.add(product_name)

                    product_obj, _ = Product.objects.get_or_create(
                        name=product_name,
                        defaults={"unit": unit, "stock": 0, "min_stock": 0},
                    )

                    # если unit отличается — обновим (но аккуратно)
                    if unit and getattr(product_obj, "unit", None) != unit:
                        product_obj.unit = unit
                        product_obj.save(update_fields=["unit"])

                    MenuItemIngredient.objects.update_or_create(
                        item=item_obj,
                        product=product_obj,
                        defaults={"amount": amount},
                    )
                    total_links += 1

                # удалим старые связи, если блюдо пересидили
                MenuItemIngredient.objects.filter(item=item_obj).exclude(product__name__in=keep).delete()

        self.stdout.write(self.style.SUCCESS(
            f"seed_menu done: items={total_items}, ingredient_links={MenuItemIngredient.objects.count()}"
        ))