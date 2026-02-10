from django.utils import timezone
from menu.models import Order, Product, BanquetMenu
from users.models import MealRequest, Subscription
from core.models import PurchaseRequest
from django.db.models import F

from datetime import datetime


def _get_seen_dt(request, key: str):
    seen = request.session.get("nav_seen", {})
    s = seen.get(key)
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except Exception:
        return None


def nav_badges(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"nav_badges": {}}

    user = request.user
    today = timezone.localdate()
    badges = {}
    role = getattr(user, "role", "student")

    # отдельно для "склада"
    seen_counts = request.session.get("nav_seen_counts", {})

    if role == "student":
        seen_dt = _get_seen_dt(request, "order_history")
        qs = Order.objects.filter(user=user, status="ready", received_by_student=False)
        badges["order_history"] = qs.filter(updated_at__gt=seen_dt).count() if seen_dt else qs.count()

        seen_dt = _get_seen_dt(request, "receive_meal")
        qs = MealRequest.objects.filter(user=user, date=today, status=MealRequest.STATUS_ISSUED)
        badges["receive_meal"] = qs.filter(issued_at__gt=seen_dt).count() if seen_dt else qs.count()

    elif role == "cook":
        seen_dt = _get_seen_dt(request, "cook_issue")
        orders = Order.objects.filter(status__in=["pending", "confirmed", "preparing"])
        meals = MealRequest.objects.filter(date=today, status=MealRequest.STATUS_REQUESTED)

        if seen_dt:
            badges["cook_issue"] = (
                orders.filter(updated_at__gt=seen_dt).count() +
                meals.filter(requested_at__gt=seen_dt).count()
            )
        else:
            badges["cook_issue"] = orders.count() + meals.count()

        # подсветка  — сравниваем количество проблемных позиций
        low_now = Product.objects.filter(stock__lt=F("min_stock")).count()
        low_seen = seen_counts.get("stock_list")
        badges["stock_list"] = low_now if low_seen is None or low_now != low_seen else 0

        seen_dt = _get_seen_dt(request, "cook_purchase")
        qs = PurchaseRequest.objects.filter(created_by=user, status__in=["new", "in_progress"])
        badges["cook_purchase"] = qs.filter(created_at__gt=seen_dt).count() if seen_dt else qs.count()

    elif role == "admin":
        seen_dt = _get_seen_dt(request, "admin_purchase")
        qs = PurchaseRequest.objects.filter(status="new")
        badges["admin_purchase"] = qs.filter(created_at__gt=seen_dt).count() if seen_dt else qs.count()

        seen_dt = _get_seen_dt(request, "admin_banquet_menus")
        qs = BanquetMenu.objects.filter(status=BanquetMenu.STATUS_PENDING)
        badges["admin_banquet_menus"] = qs.filter(created_at__gt=seen_dt).count() if seen_dt else qs.count()

        badges["admin_reports"] = (badges.get("admin_purchase", 0) + badges.get("admin_banquet_menus", 0))

    return {"nav_badges": badges}