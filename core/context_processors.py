from django.utils import timezone

from menu.models import Order, Product
from users.models import MealRequest, Subscription
from core.models import PurchaseRequest


def nav_badges(request):
    """
    Бейджи для вкладок в верхнем меню.
    Логика: показываем количество элементов, которые требуют внимания пользователя.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"nav_badges": {}}

    user = request.user
    today = timezone.localdate()
    badges = {}

    role = getattr(user, "role", "student")

    if role == "student":
        # 1) "Мои заказы" — сколько заказов готово к выдаче и ещё не получено учеником
        badges["order_history"] = Order.objects.filter(
            user=user,
            status="ready",
            received_by_student=False
        ).count()

        # 2) "Получить питание" — сколько приемов пищи выдано поваром и ждёт подтверждения ученика
        badges["receive_meal"] = MealRequest.objects.filter(
            user=user,
            date=today,
            status=MealRequest.STATUS_ISSUED
        ).count()

    elif role == "cook":
        # 1) "Выдача питания" — (а) заказы, которые надо обработать + (б) заявки на питание, которые надо выдать
        orders_to_process = Order.objects.filter(
            status__in=["pending", "confirmed", "preparing"]
        ).count()

        meals_to_issue = MealRequest.objects.filter(
            date=today,
            status=MealRequest.STATUS_REQUESTED
        ).count()

        badges["cook_issue"] = orders_to_process + meals_to_issue

        # 2) "Склад" — позиции, где остаток ниже/равен минимальному
        badges["stock_list"] = Product.objects.filter(stock__lte=models.F("min_stock")).count() if False else 0
        # ↑ нельзя использовать models.F без импорта, поэтому ниже нормальный вариант:
        try:
            from django.db.models import F
            badges["stock_list"] = Product.objects.filter(stock__lte=F("min_stock")).count()
        except Exception:
            badges["stock_list"] = 0

        # 3) "Заявка на закупку" — мои заявки, которые ещё не "Закуплено"
        badges["cook_purchase"] = PurchaseRequest.objects.filter(
            created_by=user,
            status__in=["new", "in_progress"]
        ).count()

    elif role == "admin":
        # 1) "Закупки" — новые заявки (требуют обработки)
        badges["admin_purchase"] = PurchaseRequest.objects.filter(status="new").count()

        # 2) "Абонементы" — абонементы, созданные сегодня (как “изменения”)
        badges["admin_subscriptions"] = Subscription.objects.filter(created_at__date=today).count()

        # 3) "Отчеты" — суммарный индикатор изменений
        badges["admin_reports"] = badges["admin_purchase"] + badges["admin_subscriptions"]

    return {"nav_badges": badges}
