from datetime import timedelta
from decimal import Decimal, InvalidOperation
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg, Q, F, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from menu.models import MenuItem, Product, Order, DailyMenu, BanquetMenu, OrderItem, BanquetReview
from menu.services import get_daily_items, deduct_for_items, has_ingredients
from users.models import User, Subscription, MealReceipt, MealRequest
from .models import PurchaseRequest



def home(request):
    return render(request, 'core/home.html')


def _role_required(role_name):
    def decorator(view_func):
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Требуется вход")
            if getattr(request.user, 'role', 'student') != role_name:
                return HttpResponseForbidden("Нет доступа")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


@login_required
@_role_required('admin')
def admin_reports(request):
    mark_nav_seen(request, "admin_reports")

    today = timezone.localdate()
    # период отчёта можно менять через ?days=7|14|30|90
    raw_days = (request.GET.get('days') or '').strip()
    try:
        days = int(raw_days) if raw_days else 7
    except Exception:
        days = 7
    if days not in {7, 14, 30, 90}:
        days = 7

    start = today - timedelta(days=max(0, days - 1))

    # заявки на закупку
    purchases_period = PurchaseRequest.objects.filter(created_at__date__range=(start, today))
    pending_purchases = purchases_period.filter(status="in_progress").count()

    purchase_done_qs = purchases_period.filter(status="done")
    purchase_done_cnt = purchase_done_qs.count()
    purchase_rejected_cnt = purchases_period.filter(status="rejected").count()
    purchase_cancelled_cnt = purchases_period.filter(status="cancelled").count()

    purchase_by_day = (
        purchases_period
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(
            done_cnt=Count('id', filter=Q(status='done')),
            in_progress_cnt=Count('id', filter=Q(status='in_progress')),
            rejected_cnt=Count('id', filter=Q(status='rejected')),
            cancelled_cnt=Count('id', filter=Q(status='cancelled')),
        )
        .order_by('day')
    )

    purchase_top_products = (
        purchase_done_qs
        .values('title')
        .annotate(cnt=Count('id'))
        .order_by('-cnt', 'title')[:10]
    )

    purchase_latest_done = list(
        purchase_done_qs.select_related('created_by').order_by('-created_at')[:20]
    )

    # берём заказы за период (исключаем отменённые)
    orders_qs = (
        Order.objects
        .filter(created_at__date__range=(start, today))
        .exclude(status='cancelled')
    )

    orders_total = orders_qs.count()
    banquet_orders = orders_qs.filter(order_type='banquet').count()
    regular_orders = orders_qs.filter(order_type='regular').count()

    revenue_total = orders_qs.aggregate(s=Sum('total_amount'))['s'] or 0
    banquet_revenue = orders_qs.filter(order_type='banquet').aggregate(s=Sum('total_amount'))['s'] or 0
    regular_revenue = orders_qs.filter(order_type='regular').aggregate(s=Sum('total_amount'))['s'] or 0

    # статистика по дням
    by_day = (
        orders_qs
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(
            banquet_cnt=Count('id', filter=Q(order_type='banquet')),
            regular_cnt=Count('id', filter=Q(order_type='regular')),
            revenue=Sum('total_amount'),
        )
        .order_by('day')
    )
    by_day_map = {row['day']: row for row in by_day}

    days_list = [start + timedelta(days=i) for i in range(days)]
    rows = []
    for d in days_list:
        row = by_day_map.get(d, {})
        rows.append({
            "date": d,
            "banquet_cnt": row.get("banquet_cnt", 0),
            "regular_cnt": row.get("regular_cnt", 0),
            "revenue": row.get("revenue", 0) or 0,
        })

    # топ блюд за период
    line_total = ExpressionWrapper(
        F('quantity') * F('price'),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    top_items = (
        OrderItem.objects
        .filter(order__in=orders_qs)
        .values('item__name')
        .annotate(
            qty=Sum('quantity'),
            sum=line_total and Sum(line_total),
        )
        .order_by('-qty', 'item__name')[:10]
    )

    # --- Проведённые банкеты (completed) за период ---
    completed_banquets = orders_qs.filter(order_type='banquet', status='completed')
    banquet_completed_cnt = completed_banquets.count()
    banquet_completed_revenue = completed_banquets.aggregate(s=Sum('total_amount'))['s'] or 0
    banquet_completed_guests_avg = completed_banquets.aggregate(a=Avg('guests_count'))['a'] or 0

    banquet_by_month = (
        completed_banquets
        .annotate(m=TruncMonth('created_at'))
        .values('m')
        .annotate(cnt=Count('id'), sum=Sum('total_amount'))
        .order_by('m')
    )

    banquet_top_items = (
        OrderItem.objects
        .filter(order__in=completed_banquets)
        .values('item__name')
        .annotate(qty=Sum('quantity'))
        .order_by('-qty', 'item__name')[:10]
    )

    banquet_latest = list(
        completed_banquets.select_related('user').order_by('-created_at')[:10]
    )

    # отзывы на проведённые банкеты (за период)
    banquet_reviews_qs = BanquetReview.objects.filter(order__in=completed_banquets)
    banquet_review_cnt = banquet_reviews_qs.count()
    banquet_review_avg = banquet_reviews_qs.aggregate(a=Avg('rating'))['a'] or 0
    banquet_review_latest = list(
        banquet_reviews_qs.select_related('user', 'order').order_by('-created_at')[:10]
    )

    purchase_done_latest = list(
        purchase_done_qs.select_related('created_by').order_by('-created_at')[:20]
    )

    return render(request, "core/admin_reports.html", {
        "today": today,
        "start": start,
        "days": days,
        "pending_purchases": pending_purchases,

        "purchase_done_cnt": purchase_done_cnt,
        "purchase_rejected_cnt": purchase_rejected_cnt,
        "purchase_cancelled_cnt": purchase_cancelled_cnt,
        "purchase_by_day": purchase_by_day,
        "purchase_top_products": purchase_top_products,
        "purchase_done_latest": purchase_done_latest,

        "orders_total": orders_total,
        "banquet_orders": banquet_orders,
        "regular_orders": regular_orders,

        "revenue_total": revenue_total,
        "banquet_revenue": banquet_revenue,
        "regular_revenue": regular_revenue,

        "rows": rows,
        "top_items": top_items,

        "banquet_completed_cnt": banquet_completed_cnt,
        "banquet_completed_revenue": banquet_completed_revenue,
        "banquet_completed_guests_avg": banquet_completed_guests_avg,
        "banquet_by_month": banquet_by_month,
        "banquet_top_items": banquet_top_items,
        "banquet_latest": banquet_latest,

        "banquet_review_cnt": banquet_review_cnt,
        "banquet_review_avg": banquet_review_avg,
        "banquet_review_latest": banquet_review_latest,
    })


@login_required
@_role_required('admin')
def admin_banquet_stats(request):
    """Статистика по уже проведённым банкетам."""
    mark_nav_seen(request, "admin_banquet_stats")

    today = timezone.localdate()
    raw_days = (request.GET.get('days') or '').strip()
    try:
        days = int(raw_days) if raw_days else 30
    except Exception:
        days = 30
    if days not in {7, 14, 30, 90, 180, 365}:
        days = 30

    start = today - timedelta(days=max(0, days - 1))

    qs = (
        Order.objects
        .filter(order_type='banquet')
        .filter(created_at__date__range=(start, today))
        .filter(status='completed')
        .order_by('-created_at')
    )

    total_cnt = qs.count()
    revenue = qs.aggregate(s=Sum('total_amount'))['s'] or 0
    guests_avg = qs.aggregate(a=Avg('guests_count'))['a'] or 0

    by_month = (
        qs.annotate(m=TruncMonth('created_at'))
        .values('m')
        .annotate(cnt=Count('id'), sum=Sum('total_amount'))
        .order_by('m')
    )

    top_items = (
        OrderItem.objects
        .filter(order__in=qs)
        .values('item__name')
        .annotate(qty=Sum('quantity'))
        .order_by('-qty', 'item__name')[:10]
    )

    latest = list(qs.select_related('user')[:25])

    return render(request, 'core/admin_banquet_stats.html', {
        'today': today,
        'start': start,
        'days': days,
        'total_cnt': total_cnt,
        'revenue': revenue,
        'guests_avg': guests_avg,
        'by_month': by_month,
        'top_items': top_items,
        'latest': latest,
    })


@login_required
@_role_required('admin')
def admin_banquets_done(request):
    """Обзор проведённых банкетов (заказы-банкеты со статусом completed)."""
    mark_nav_seen(request, "admin_banquets_done")

    days_options = [7, 14, 30, 90, 180, 365]

    today = timezone.localdate()
    raw_days = (request.GET.get('days') or '').strip()
    try:
        days = int(raw_days) if raw_days else 30
    except Exception:
        days = 30
    if days not in days_options:
        days = 30
    start = today - timedelta(days=max(0, days - 1))

    qs = (
        Order.objects
        .filter(order_type='banquet', status='completed')
        .filter(created_at__date__range=(start, today))
        .select_related('user')
        .order_by('-created_at')
    )

    total_cnt = qs.count()
    revenue = qs.aggregate(s=Sum('total_amount'))['s'] or 0
    guests_avg = qs.aggregate(a=Avg('guests_count'))['a'] or 0

    latest = list(qs[:50])

    return render(request, 'core/admin_banquets_done.html', {
        'today': today,
        'start': start,
        'days': days,
        'days_options': days_options,
        'total_cnt': total_cnt,
        'revenue': revenue,
        'guests_avg': guests_avg,
        'latest': latest,
    })


@login_required
@_role_required('admin')
def admin_banquet_detail(request, order_id: int):
    """Карточка проведённого банкета + отзыв (если есть)."""
    mark_nav_seen(request, "admin_banquet_detail")

    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related('orderitem_set__item'),
        pk=order_id,
        order_type='banquet',
    )

    review = getattr(order, 'banquet_review', None)
    return render(request, 'core/admin_banquet_detail.html', {
        'order': order,
        'review': review,
    })


def mark_nav_seen(request, key: str):
    seen = request.session.get("nav_seen", {})
    seen[key] = timezone.now().isoformat()
    request.session["nav_seen"] = seen
    request.session.modified = True


@login_required
def cook_issue(request):
    mark_nav_seen(request, "cook_issue")
    if getattr(request.user, 'role', '') not in ('cook', 'admin'):
        return HttpResponseForbidden("Нет доступа")

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
        order_id = request.POST.get("order_id")

        if action in {"order_ready", "order_complete", "order_cancel", "set_order_status"}:
            if not order_id:
                messages.error(request, "Неверные данные.")
                return redirect("cook_issue")

            order = get_object_or_404(Order, id=order_id)

            if action == "order_ready":
                order.status = "ready"
                order.save()
                messages.success(request, f"Заказ #{order.id} отмечен как готовый.")
                return redirect("cook_issue")

            if action == "order_complete":
                if order.status != "ready":
                    messages.error(request, "Сначала отметьте заказ как готовый.")
                    return redirect("cook_issue")
                order.status = "completed"
                order.received_by_student = True
                order.received_at = timezone.now()
                order.save()
                messages.success(request, f"Заказ #{order.id} выдан.")
                return redirect("cook_issue")

            if action == "order_cancel":
                order.status = "cancelled"
                order.save()
                messages.success(request, f"Заказ #{order.id} отменён.")
                return redirect("cook_issue")

            # совместимость со старым режимом (вдруг где-то остался select)
            if action == "set_order_status":
                status = request.POST.get("status")
                valid_statuses = {k for k, _ in Order.STATUS_CHOICES}
                if status not in valid_statuses:
                    messages.error(request, "Некорректный статус.")
                    return redirect("cook_issue")
                order.status = status
                order.save()
                messages.success(request, f"Статус заказа #{order.id} обновлён.")
                return redirect("cook_issue")

        elif action == "issue_meal":
            user_id = request.POST.get("user_id")
            meal_type = request.POST.get("meal_type")  # breakfast/lunch
            student = get_object_or_404(User, id=user_id)
            today = timezone.localdate()

            # Запрещаем выдачу, если меню дня не задано
            items = get_daily_items(today, meal_type)
            if not items:
                messages.error(
                    request,
                    "Не задано меню дня на сегодня. "
                )
                return redirect("cook_issue")

            # Проверка абонемента
            has_sub = Subscription.objects.filter(
                user=student,
                start_date__lte=today,
                end_date__gte=today,
                plan=meal_type,
            ).exists()

            if not has_sub:
                messages.error(request, "У клиента нет активного абонемента на этот тип питания на сегодня.")
                return redirect("cook_issue")

            # Создаём/берём заявку
            mr, created = MealRequest.objects.get_or_create(
                user=student,
                date=today,
                meal_type=meal_type,
                defaults={
                    "status": MealRequest.STATUS_REQUESTED,  # важно!
                    "requested_at": timezone.now(),
                }
            )

            # Нельзя повторно "выдать", если уже подтверждено
            if mr.status == MealRequest.STATUS_CONFIRMED:
                messages.warning(request, "Клиент уже подтвердил получение. Повторная выдача невозможна.")
                return redirect("cook_issue")

            # Списываем продукты один раз
            if not mr.stock_deducted:
                not_enough, _ = deduct_for_items(items)
                if not_enough:
                    messages.error(request, "Недостаточно продуктов:\n" + "\n".join(not_enough))
                    return redirect("cook_issue")
                mr.stock_deducted = True

            # Фиксируем выдачу
            mr.status = MealRequest.STATUS_ISSUED
            mr.issued_by = request.user
            mr.issued_at = timezone.now()
            mr.save(update_fields=["status", "issued_by", "issued_at", "stock_deducted"])

            messages.success(request, f"Выдано: {student.username} — {meal_type} ({today}).")
            return redirect("cook_issue")

            # выдача питания
            mr.status = MealRequest.STATUS_ISSUED
            mr.issued_by = request.user
            mr.issued_at = timezone.now()
            mr.save(update_fields=["status", "issued_by", "issued_at", "stock_deducted"])

            messages.success(request, f"Выдано: {student.username} — {meal_type} ({today}).")

            return redirect("cook_issue")

        elif action == "issue_meal_request":
            req_id = request.POST.get("request_id")
            mr = get_object_or_404(MealRequest, id=req_id)
            items = get_daily_items(mr.date, mr.meal_type)
            if not items:
                messages.error(
                    request,
                    "Не задано меню дня на сегодня. "
                    "Задайте его в админке (DailyMenu) и выберите блюда для завтрака/обеда."
                )
                return redirect("cook_issue")

            if not mr.stock_deducted:
                not_enough, _ = deduct_for_items(items)
                if not_enough:
                    messages.error(request, "Недостаточно продуктов:\n" + "\n".join(not_enough))
                    return redirect("cook_issue")
                mr.stock_deducted = True

            if mr.status != MealRequest.STATUS_REQUESTED:
                messages.warning(request, "Можно выдавать только заявки в статусе 'Запрошено'.")
                return redirect("cook_issue")

            mr.status = MealRequest.STATUS_ISSUED
            mr.issued_by = request.user
            mr.issued_at = timezone.now()
            mr.save(update_fields=['status', 'issued_by', 'issued_at', 'stock_deducted'])

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
    mark_nav_seen(request, "cook_purchase")
    draft_items = PurchaseRequest.objects.filter(
        created_by=request.user, status="new"
    )

    # Отправленные/в работе/закуплено
    sent_items = PurchaseRequest.objects.filter(
        created_by=request.user
    ).exclude(status="new")

    # Отправить администратору
    if request.method == "POST" and request.POST.get("action") == "send":
        draft_items.update(status="in_progress")
        messages.success(request, "Заявка отправлена администратору.")
        return redirect("cook_purchase")

    # Удалить позицию из черновика
    if request.method == "POST" and request.POST.get("action") == "delete":
        pr_id = request.POST.get("id")
        PurchaseRequest.objects.filter(id=pr_id, created_by=request.user, status="new").delete()
        return redirect("cook_purchase")

    # Отменить отправленную заявку (до подтверждения администратором)
    if request.method == "POST" and request.POST.get("action") == "cancel":
        pr_id = request.POST.get("id")
        PurchaseRequest.objects.filter(
            id=pr_id,
            created_by=request.user,
            status="in_progress",
        ).update(status="cancelled")
        return redirect("cook_purchase")

    return render(request, "core/cook_purchase.html", {
        "draft_items": draft_items,
        "sent_items": sent_items,
    })


@login_required
@_role_required("admin")
def admin_purchase(request):
    mark_nav_seen(request, "admin_purchase")
    items = PurchaseRequest.objects.filter(status="in_progress").select_related("created_by")

    if request.method == "POST" and request.POST.get("action") == "reject":
        pr_id = request.POST.get("id")
        pr = get_object_or_404(PurchaseRequest, id=pr_id, status="in_progress")
        pr.status = "rejected"
        pr.save(update_fields=["status"])
        messages.info(request, "Заявка отклонена.")
        return redirect("admin_purchase")

    if request.method == "POST" and request.POST.get("action") == "accept":
        pr_id = request.POST.get("id")
        pr = get_object_or_404(PurchaseRequest, id=pr_id, status="in_progress")

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

        # Создаём/находим продукт
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

        stock_field = Product._meta.get_field("stock")
        dp = getattr(stock_field, "decimal_places", 0) or 0

        exp = Decimal("1").scaleb(-dp)
        try:
            qty = qty.quantize(exp)
        except InvalidOperation:
            messages.error(request, "Количество нельзя привести к формату склада (слишком много знаков после запятой).")
            return redirect("admin_purchase")

        current = product.stock if product.stock is not None else Decimal("0")
        new_stock = current + qty

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
    rejected_items = PurchaseRequest.objects.filter(status__in=["rejected", "cancelled"]).select_related("created_by")[:200]

    return render(request, "core/admin_purchase.html", {
        "items": items,
        "done_items": done_items,
        "rejected_items": rejected_items,
    })


@login_required
def cook_banquet_menus(request):
    mark_nav_seen(request, "cook_banquet_menus")
    if getattr(request.user, 'role', '') != 'cook':
        return HttpResponseForbidden("Доступно только повару")

    # все блюда (закуски/основные/напитки) для составления банкета
    items = (
        MenuItem.objects
        .select_related('category')
        .prefetch_related('ingredients__product')
        .order_by('category__order', 'name')
    )

    not_available_ids = set()
    for it in items:
        if not has_ingredients(it):
            not_available_ids.add(it.id)

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        description = (request.POST.get('description') or '').strip()

        selected_ids = [i for i in request.POST.getlist('items') if i.isdigit()]
        selected_ids = [int(i) for i in selected_ids if int(i) not in not_available_ids]

        if not name:
            messages.error(request, 'Укажите название банкетного меню.')
        else:
            bm = BanquetMenu.objects.create(
                name=name,
                description=description,
                created_by=request.user,
                status=BanquetMenu.STATUS_PENDING,
                is_active=False,
            )
            bm.items.set(MenuItem.objects.filter(id__in=selected_ids))

            messages.success(request, 'Банкетное меню отправлено администратору на рассмотрение.')
            return redirect('cook_banquet_menus')

    my_menus = (
        BanquetMenu.objects
        .filter(created_by=request.user)
        .prefetch_related('items')
        .order_by('-created_at')
    )

    # группируем по разделам (в seed: Завтраки/Обеды/Напитки)
    groups = {
        'snacks': [it for it in items if (it.category and it.category.name == 'Завтраки')],
        'main': [it for it in items if (it.category and it.category.name == 'Обеды')],
        'drinks': [it for it in items if (it.category and it.category.name == 'Напитки')],
        'other': [it for it in items if not it.category or it.category.name not in {'Завтраки', 'Обеды', 'Напитки'}],
    }

    return render(request, 'core/cook_banquet_menus.html', {
        'groups': groups,
        'not_available_ids': not_available_ids,
        'my_menus': my_menus,
    })


@login_required
@_role_required('admin')
def admin_banquet_menus(request):
    if request.method == 'POST':
        menu_id = (request.POST.get('menu_id') or '').strip()
        action = (request.POST.get('action') or '').strip()

        if menu_id.isdigit():
            bm = get_object_or_404(BanquetMenu, id=int(menu_id))

            if action == 'approve':
                bm.status = BanquetMenu.STATUS_APPROVED
                bm.is_active = True
                bm.reviewed_by = request.user
                bm.reviewed_at = timezone.now()
                bm.save()
                messages.success(request, f'Меню "{bm.name}" принято.')

            elif action == 'reject':
                bm.status = BanquetMenu.STATUS_REJECTED
                bm.is_active = False
                bm.reviewed_by = request.user
                bm.reviewed_at = timezone.now()
                bm.save()
                messages.warning(request, f'Меню "{bm.name}" отклонено.')

    pending = (
        BanquetMenu.objects
        .filter(status=BanquetMenu.STATUS_PENDING)
        .select_related('created_by')
        .prefetch_related('items')
        .order_by('-created_at')
    )

    return render(request, 'core/admin_banquet_menus.html', {
        'pending': pending,
    })

