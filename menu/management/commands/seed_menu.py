import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from menu.models import Category, MenuItem


CATEGORY_ORDER = {
    "Закуски": 10,
    "Основные блюда": 20,
    "Напитки": 30,
}


class Command(BaseCommand):
    help = "Seed menu from menu/data/menu_seed.json (safe to run multiple times)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete ALL menu items and categories before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        data_path = Path(__file__).resolve().parents[3] / "data" / "menu_seed.json"
        if not data_path.exists():
            raise CommandError(f"Seed file not found: {data_path}")

        try:
            data = json.loads(data_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise CommandError(f"Failed to read/parse JSON: {e}")

        if options["reset"]:
            MenuItem.objects.all().delete()
            Category.objects.all().delete()

        created_categories = 0
        created_items = 0
        updated_items = 0

        for category_name, items in data.items():
            category, cat_created = Category.objects.get_or_create(
                name=category_name,
                defaults={
                    "description": "",
                    "order": CATEGORY_ORDER.get(category_name, 100),
                },
            )
            if not cat_created:
                # ensure nice ordering for main categories
                desired_order = CATEGORY_ORDER.get(category_name)
                if desired_order is not None and category.order != desired_order:
                    category.order = desired_order
                    category.save(update_fields=["order"])
            else:
                created_categories += 1

            for item in items:
                name = (item.get("name") or "").strip()
                if not name:
                    continue

                defaults = {
                    "category": category,
                    "price": item.get("price", 0),
                    "description": item.get("description", "") or "",
                    "allergens": (item.get("allergens") or "").strip(),
                    "is_available": bool(item.get("is_available", True)),
                    "calories": item.get("calories"),
                }

                obj, created = MenuItem.objects.get_or_create(name=name, defaults=defaults)

                if created:
                    created_items += 1
                    continue

                # sync fields if changed
                changed_fields = []
                for field, value in defaults.items():
                    if getattr(obj, field) != value:
                        setattr(obj, field, value)
                        changed_fields.append(field)

                if changed_fields:
                    obj.save(update_fields=changed_fields)
                    updated_items += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_menu: categories +{created_categories}; items +{created_items}; updated {updated_items}."
            )
        )
