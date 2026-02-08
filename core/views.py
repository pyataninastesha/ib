from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count
from django.conf import settings

from core.models import PurchaseRequest
from menu.models import DailyMenu, MenuItem, Product, Order
from menu.services import deduct_for_items
from menu.views import _role_required
from users.models import MealRequest as UserMealRequest, MealReceipt as UserMealReceipt, User
from core.eco_planning import compute_suggested_portions
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.urls import reverse

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count

from menu.models import DailyMenu, MenuItem, Product
from users.models import MealRequest as UserMealRequest, MealReceipt as UserMealReceipt
from core.eco_planning import compute_suggested_portions
from datetime import timedelta
from decimal import Decimal
from django.urls import reverse


from users.models import MealRequest, MealReceipt, Subscription
from menu.models import DailyMenu, MenuItem
from core.eco_planning import compute_suggested_portions


def home(request):
    return render(request, "core/home.html")

def admin_reports(request):
    # Логика для создания отчета
    return render(request, "core/admin_reports.html")

def organization_settings(request):
    # Логика для отображения настроек организации
    return render(request, "core/organization_settings.html")

def eco_dashboard(request):
    # Логика для отображения данных о перерасходах и углеродном следе
    return render(request, "core/eco_dashboard.html")

def get_daily_items(day, meal_type, organization=None):
    """Return DailyMenu items for day and meal_type.

    NOTE: DailyMenu in this project stores two M2M sets: breakfast_items and lunch_items
    (there is no 'meal_type' field on DailyMenu).
    """
    from menu.models import DailyMenu  # local import to avoid circular imports

    qs = DailyMenu.objects.filter(date=day)
    if organization is not None and hasattr(DailyMenu, "organization_id"):
        qs = qs.filter(organization=organization)
    daily = qs.first()
    if not daily:
        return []

    # meal_type strings in system: 'breakfast' or 'lunch'
    if meal_type == "breakfast" and hasattr(daily, "breakfast_items"):
        return list(daily.breakfast_items.all())
    if meal_type == "lunch" and hasattr(daily, "lunch_items"):
        return list(daily.lunch_items.all())

    # Fallback: union of both sets
    items = []
    if hasattr(daily, "breakfast_items"):
        items += list(daily.breakfast_items.all())
    if hasattr(daily, "lunch_items"):
        items += list(daily.lunch_items.all())
    return items


def create_organization(request):
    if request.method == 'POST':
        name = request.POST['name']
        org_type = request.POST['org_type']
        goals = request.POST['goals']
        avg_portions_per_day = request.POST['avg_portions_per_day']

        # Генерируем код подключения
        join_code = Organization.generate_join_code()

        organization = Organization.objects.create(
            name=name,
            org_type=org_type,
            goals=goals,
            avg_portions_per_day=avg_portions_per_day,
            join_code=join_code
        )

        # Переходим к отображению организации
        return redirect('organization_details', pk=organization.pk)

    return render(request, 'core/create_organization.html')


def cook_issue(request):
    if getattr(request.user, 'role', '') != 'cook':
        return HttpResponseForbidden("Доступно только повару")

    today = timezone.localdate()

    # заказы из корзины
    orders = (
        Order.objects
        .select_related('user')
        .prefetch_related('orderitem_set__item')
        .order_by('-created_at')[:50]
    )

    # абонементы на сегодня
    subs_today = (
        Subscription.objects
        .select_related('user')
        .filter(start_date__lte=today, end_date__gte=today)
        .order_by('user__username', '-start_date')
    )

    # собираем список учеников (по одному на пользователя) + какие приемы пищи доступны
    subs_by_user = {}
    for sub in subs_today:
        uid = sub.user_id
        if uid not in subs_by_user:
            subs_by_user[uid] = {'user': sub.user, 'breakfast': None, 'lunch': None}
        if sub.plan == Subscription.PLAN_BREAKFAST and subs_by_user[uid]['breakfast'] is None:
            subs_by_user[uid]['breakfast'] = sub
        if sub.plan == Subscription.PLAN_LUNCH and subs_by_user[uid]['lunch'] is None:
            subs_by_user[uid]['lunch'] = sub

    # уже выдано/подтверждено на сегодня
    issued_map = {
        (mr.user_id, mr.meal_type): mr
        for mr in MealRequest.objects.filter(date=today).exclude(status=MealRequest.STATUS_CANCELLED)
    }
    confirmed_set = set(
        MealReceipt.objects.filter(date=today).values_list('user_id', 'meal_type')
    )

    meal_requests = (
        MealRequest.objects
        .select_related('user')
        .filter(date=today, status=MealRequest.STATUS_REQUESTED)
        .order_by('meal_type', 'requested_at')
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "set_order_status":
            order_id = request.POST.get("order_id")
            status = request.POST.get("status")
            order = get_object_or_404(Order, id=order_id)

            valid_statuses = {k for k, _ in Order.STATUS_CHOICES}
            if status not in valid_statuses:
                messages.error(request, "Некорректный статус.")
                return redirect("cook_issue")

            order.status = status
            order.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Статус заказа #{order.id} обновлён.")
            return redirect("cook_issue")


        elif action == "issue_meal":

            user_id = request.POST.get("user_id")

            meal_type = request.POST.get("meal_type")  # breakfast/lunch

            student = get_object_or_404(User, id=user_id)

            today = timezone.localdate()

            # Проверяем, что у ученика есть подписка на этот прием пищи сегодня

            has_sub = Subscription.objects.filter(

                user=student,

                start_date__lte=today,

                end_date__gte=today,

                plan=meal_type,  # ВАЖНО: завтрак/обед отдельно

            ).exists()

            if not has_sub:
                messages.error(request, "У ученика нет активного абонемента на этот тип питания на сегодня.")

                return redirect("cook_issue")

            # создаём или берём заявку на сегодня

            mr, created = MealRequest.objects.get_or_create(
                user=student,
                date=today,
                meal_type=meal_type,
                defaults={
                    "status": MealRequest.STATUS_ISSUED,
                    "issued_by": request.user,
                    "issued_at": timezone.now(),
                    "requested_at": timezone.now(),
                }
            )

            # Нельзя повторно "выдать", если уже подтверждено учеником
            if mr.status == MealRequest.STATUS_CONFIRMED:
                messages.warning(request, "Ученик уже подтвердил получение. Повторная выдача невозможна.")
                return redirect("cook_issue")

            # === СПИСАНИЕ ПРОДУКТОВ СО СКЛАДА (ТОЛЬКО 1 РАЗ) ===
            if not mr.stock_deducted:
                items = get_daily_items(today, meal_type, organization=getattr(request.user, "organization", None))

                if not items:
                    messages.error(
                        request,
                        "Не задано меню дня на сегодня. "
                        "Задайте его в админке (DailyMenu) и выберите блюда для завтрака/обеда."
                    )
                    return redirect("cook_issue")

                not_enough, _ = deduct_for_items(items)
                if not_enough:
                    messages.error(request, "Недостаточно продуктов:\n" + "\n".join(not_enough))
                    return redirect("cook_issue")

                mr.stock_deducted = True

            # === ВЫДАЧА ПИТАНИЯ ===
            mr.status = MealRequest.STATUS_ISSUED
            mr.issued_by = request.user
            mr.issued_at = timezone.now()
            mr.save(update_fields=["status", "issued_by", "issued_at", "stock_deducted"])

            messages.success(request, f"Выдано: {student.username} — {meal_type} ({today}).")

            return redirect("cook_issue")

        elif action == "issue_meal_request":
            req_id = request.POST.get("request_id")
            mr = get_object_or_404(MealRequest, id=req_id)

            if mr.status != MealRequest.STATUS_REQUESTED:
                messages.warning(request, "Можно выдавать только заявки в статусе 'Запрошено'.")
                return redirect("cook_issue")

            mr.status = MealRequest.STATUS_ISSUED
            mr.issued_by = request.user
            mr.issued_at = timezone.now()
            mr.save(update_fields=['status', 'issued_by', 'issued_at'])

            messages.success(request, f"Выдано: {mr.user.username} — {mr.get_meal_type_display()} ({mr.date}).")
            return redirect("cook_issue")

    status_choices = Order.STATUS_CHOICES

    # “таблица выдачи” для шаблона
    subs_rows = []
    for uid, row in subs_by_user.items():
        user = row['user']

        def cell(meal_type):
            if meal_type == 'breakfast' and not row['breakfast']:
                return {'available': False}
            if meal_type == 'lunch' and not row['lunch']:
                return {'available': False}

            if (uid, meal_type) in confirmed_set:
                return {'available': True, 'state': 'confirmed'}

            mr = issued_map.get((uid, meal_type))
            if mr and mr.status == MealRequest.STATUS_ISSUED:
                return {'available': True, 'state': 'issued', 'mr': mr}

            return {'available': True, 'state': 'none'}

        subs_rows.append({
            'user': user,
            'breakfast': cell('breakfast'),
            'lunch': cell('lunch'),
        })

    return render(request, 'core/cook_issue.html', {
        'orders': orders,
        'status_choices': status_choices,
        'today': today,
        'meal_requests': meal_requests,
        'subs_rows': subs_rows,
    })


@login_required
@_role_required("cook")
def cook_purchase(request):
    # Черновик = status "new"
    org = getattr(request.user, 'organization', None)

    draft_items = PurchaseRequest.objects.filter(
        created_by=request.user, status="new"
    )
    if org:
        draft_items = draft_items.filter(organization=org)

    # Отправленные/в работе/закуплено = всё кроме new
    sent_items = PurchaseRequest.objects.filter(
        created_by=request.user
    ).exclude(status="new")
    if org:
        sent_items = sent_items.filter(organization=org)

    # Отправить администратору -> in_progress
    if request.method == "POST" and request.POST.get("action") == "send":
        draft_items.update(status="in_progress")
        messages.success(request, "Заявка отправлена администратору.")
        return redirect("cook_purchase")

    # Удалить позицию из черновика
    if request.method == "POST" and request.POST.get("action") == "delete":
        pr_id = request.POST.get("id")
        qs = PurchaseRequest.objects.filter(id=pr_id, created_by=request.user, status="new")
        if org:
            qs = qs.filter(organization=org)
        qs.delete()
        return redirect("cook_purchase")

    return render(request, "core/cook_purchase.html", {
        "draft_items": draft_items,
        "sent_items": sent_items,
    })


@login_required
@_role_required("admin")
def admin_purchase(request):
    org = getattr(request.user, 'organization', None)
    items = PurchaseRequest.objects.filter(status="in_progress").select_related("created_by")
    if org:
        items = items.filter(organization=org)

    if request.method == "POST" and request.POST.get("action") == "accept":
        pr_id = request.POST.get("id")
        pr = get_object_or_404(PurchaseRequest, id=pr_id, status="in_progress")

        # ---- 1) Парсим количество безопасно ----
        qty_raw = (pr.quantity or "").strip().replace(",", ".")
        qty_clean = re.sub(r"[^0-9.\-]", "", qty_raw)

        try:
            qty = Decimal(qty_clean)
        except (InvalidOperation, ValueError):
            messages.error(
                request,
                f"Нельзя принять заявку: количество указано неверно («{pr.quantity}»). "
                f"Исправь количество (пример: 5 или 0.5)."
            )
            return redirect("admin_purchase")

        if qty <= 0:
            messages.error(request, "Количество должно быть больше 0.")
            return redirect("admin_purchase")

        # ---- 2) Создаём/находим продукт ----
        product, _ = Product.objects.get_or_create(
            name=pr.title,
            defaults={"unit": pr.unit or "г"}
        )

        if pr.unit and product.unit != pr.unit:
            messages.warning(
                request,
                f"Ед. изм. на складе: {product.unit}. В заявке: {pr.unit}. "
                f"Пополнение всё равно выполнено."
            )

        # ---- 3) Приводим к формату stock (decimal_places/max_digits) и валидируем ----
        stock_field = Product._meta.get_field("stock")
        dp = getattr(stock_field, "decimal_places", 0) or 0

        # округление до нужных decimal_places
        exp = Decimal("1").scaleb(-dp)  # например dp=2 -> Decimal('0.01')
        try:
            qty = qty.quantize(exp)  # qty -> строго в формат поля stock
        except InvalidOperation:
            messages.error(request, "Количество нельзя привести к формату склада (слишком много знаков после запятой).")
            return redirect("admin_purchase")

        current = product.stock if product.stock is not None else Decimal("0")
        new_stock = current + qty

        # проверка, что число влезает в max_digits/decimal_places
        try:
            stock_field.clean(new_stock, product)
        except ValidationError:
            messages.error(
                request,
                "Нельзя принять заявку: итоговое значение на складе не помещается в формат поля stock "
                "(слишком большое число или слишком много знаков после запятой)."
            )
            return redirect("admin_purchase")

        product.stock = new_stock
        product.save(update_fields=["stock"])

        pr.status = "done"
        pr.save(update_fields=["status"])

        messages.success(request, f"Заявка принята. На склад добавлено: {product.name} +{qty} {product.unit}.")
        return redirect("admin_purchase")

    done_items = PurchaseRequest.objects.filter(status="done").select_related("created_by")[:200]

    return render(request, "core/admin_purchase.html", {
        "items": items,
        "done_items": done_items,
    })



@login_required
@_role_required('admin')
def admin_subscriptions(request):
    """Администратор: контроль абонементов и фактов получения."""
    date_str = (request.GET.get("date") or "").strip()
    if date_str:
        try:
            day = timezone.datetime.fromisoformat(date_str).date()
        except ValueError:
            day = timezone.localdate()
            messages.warning(request, "Некорректная дата. Показан сегодняшний день.")
    else:
        day = timezone.localdate()

    subs = (
        Subscription.objects
        .select_related("user")
        .filter(start_date__lte=day, end_date__gte=day)
        .order_by("user__username", "plan")
    )

    subs_by_user = {}
    for s in subs:
        uid = s.user_id
        if uid not in subs_by_user:
            subs_by_user[uid] = {"user": s.user, "breakfast": False, "lunch": False}
        if s.plan == Subscription.PLAN_BREAKFAST:
            subs_by_user[uid]["breakfast"] = True
        if s.plan == Subscription.PLAN_LUNCH:
            subs_by_user[uid]["lunch"] = True

    req_map = {
        (r.user_id, r.meal_type): r
        for r in MealRequest.objects.filter(date=day).select_related("user")
    }

    confirmed_set = set(
        MealReceipt.objects.filter(date=day).values_list("user_id", "meal_type")
    )

    rows = []
    for uid, row in subs_by_user.items():
        user = row["user"]

        def cell(meal_type: str):
            if not row.get(meal_type):
                return {"state": "no_sub"}
            if (uid, meal_type) in confirmed_set:
                return {"state": "confirmed"}
            mr = req_map.get((uid, meal_type))
            if not mr:
                return {"state": "none"}
            return {"state": mr.status, "mr": mr}

        rows.append({
            "user": user,
            "breakfast": cell("breakfast"),
            "lunch": cell("lunch"),
        })

    total_active_users = len(rows)
    total_active_meals = sum(
        (1 if r["breakfast"]["state"] != "no_sub" else 0) +
        (1 if r["lunch"]["state"] != "no_sub" else 0)
        for r in rows
    )

    return render(request, "core/admin_subscriptions.html", {
        "day": day,
        "rows": rows,
        "total_active_users": total_active_users,
        "total_active_meals": total_active_meals,
    })


@login_required
@_role_required('cook')
def cook_daily_menu(request):
    # --- 1) выбранная дата из GET/POST ---
    date_str = (request.GET.get("date") or request.POST.get("date") or "").strip()

    if date_str:
        try:
            selected_day = timezone.datetime.fromisoformat(date_str).date()
        except ValueError:
            selected_day = timezone.localdate()
            messages.warning(request, "Некорректная дата. Показан сегодняшний день.")
    else:
        selected_day = timezone.localdate()

    # --- 2) отдельный DailyMenu на каждую дату ---
    org = getattr(request.user, 'organization', None)
    dm, _ = DailyMenu.objects.get_or_create(date=selected_day, organization=org)

    # --- 3) получаем блюда для выбора (важно: именно это у тебя сейчас “пропадает”) ---
    # ВАЖНО: в твоём проекте нет meal_type, поэтому делим по названиям категорий.
    # Если у тебя категории называются иначе — поменяй строки "Завтраки"/"Обеды" на свои.
    breakfast_items = MenuItem.objects.filter(
        category__name__iexact="Завтраки"
    ).prefetch_related("ingredients__product").order_by("name")

    lunch_items = MenuItem.objects.filter(
        category__name__iexact="Обеды"
    ).prefetch_related("ingredients__product").order_by("name")

    # --- 4) функция проверки ингредиентов (упрощённо: stock >= amount) ---
    def has_ingredients(menu_item: MenuItem) -> bool:
        for ing in menu_item.ingredients.all():
            need = ing.amount if ing.amount is not None else Decimal("0")
            have = ing.product.stock if ing.product.stock is not None else Decimal("0")
            if have < need:
                return False
        return True

    not_available_ids = set()
    for it in list(breakfast_items) + list(lunch_items):
        if not has_ingredients(it):
            not_available_ids.add(it.id)

    # --- 5) сохраняем выбранные блюда (дату не меняем) ---
    if request.method == "POST":
        # берем выбранные id из чекбоксов
        b_ids = request.POST.getlist("breakfast_items")
        l_ids = request.POST.getlist("lunch_items")

        # на всякий случай: запрещаем сохранять недоступные блюда (даже если кто-то руками отправит POST)
        b_ids = [i for i in b_ids if i.isdigit() and int(i) not in not_available_ids]
        l_ids = [i for i in l_ids if i.isdigit() and int(i) not in not_available_ids]

        dm.breakfast_items.set(MenuItem.objects.filter(id__in=b_ids))
        dm.lunch_items.set(MenuItem.objects.filter(id__in=l_ids))

        # сохраняем план порций
        try:
            dm.planned_breakfast_portions = int(request.POST.get('planned_breakfast_portions') or 0)
        except ValueError:
            dm.planned_breakfast_portions = 0
        try:
            dm.planned_lunch_portions = int(request.POST.get('planned_lunch_portions') or 0)
        except ValueError:
            dm.planned_lunch_portions = 0
        dm.save(update_fields=['planned_breakfast_portions','planned_lunch_portions'])

        messages.success(request, "План производства сохранён.")
        return redirect(f"{reverse('cook_daily_menu')}?date={selected_day.isoformat()}")

    # --- 6) подгружаем меню дня с ингредиентами для блока “что будет выдано” ---
    dm = DailyMenu.objects.filter(date=selected_day, organization=org).prefetch_related(
        "breakfast_items__ingredients__product",
        "lunch_items__ingredients__product",
    ).first()

    all_menus = DailyMenu.objects.filter(organization=org).prefetch_related(
        "breakfast_items__ingredients__product",
        "lunch_items__ingredients__product",
    ).order_by("-date")

    
    # --- превью рекомендаций (не сохраняет) ---
    b_suggest_preview, b_inputs_preview = compute_suggested_portions(selected_day, MealReceipt.MEAL_BREAKFAST, organization=org)
    l_suggest_preview, l_inputs_preview = compute_suggested_portions(selected_day, MealReceipt.MEAL_LUNCH, organization=org)

    return render(request, "core/cook_daily_menu.html", {
        "today": selected_day,            # если где-то ещё используется today
        "selected_day": selected_day,     # для input date и заголовка
        "daily_menu": dm,
        "b_suggest_preview": b_suggest_preview,
        "b_inputs_preview": b_inputs_preview,
        "l_suggest_preview": l_suggest_preview,
        "l_inputs_preview": l_inputs_preview,
        "all_menus": all_menus,
        "breakfast_items": breakfast_items,
        "lunch_items": lunch_items,
        "not_available_ids": not_available_ids,
    })
from core.eco_planning import compute_suggested_portions

def compute_plan_for_day(day, org):
    b_suggest, b_inputs = compute_suggested_portions(day, MealReceipt.MEAL_BREAKFAST, organization=org)
    l_suggest, l_inputs = compute_suggested_portions(day, MealReceipt.MEAL_LUNCH, organization=org)
    return b_suggest, l_suggest, b_inputs, l_inputs

def admin_dashboard(request):
    # Example admin dashboard view
    return render(request, "core/admin_dashboard.html")
