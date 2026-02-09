from django.db import IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.http import HttpResponseForbidden
from django.db import transaction

from core.views import mark_nav_seen
from menu.models import BanquetMenu, Order, OrderItem
from .forms import CustomUserCreationForm, CustomAuthenticationForm, ProfileUpdateForm
from .models import Subscription, MealReceipt, MealRequest
from .models import BalanceTopUp


def _redirect_by_role(user):
    role = getattr(user, 'role', 'student')
    if role == 'cook':
        return redirect('cook_banquet_menus')
    if role == 'admin':
        return redirect('admin_dashboard')
    return redirect('home')


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return _redirect_by_role(user)
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    if getattr(request.user, 'role', 'student') != 'student':
        return HttpResponseForbidden('Пополнение баланса доступно только ученикам')
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {username}!')
                return _redirect_by_role(user)
    else:
        form = CustomAuthenticationForm()
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Вы вышли из системы.')
    return redirect('home')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлен!')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user)

    role = getattr(request.user, 'role', 'student')

    return render(request, 'users/profile.html', {
        'form': form,
        'is_cook': role == 'cook',
        'is_admin': role == 'admin',
        'is_student': role == 'student',
    })


@login_required
def wallet_view(request):

    if request.method == 'POST':
        raw = (request.POST.get('amount') or '').replace(',', '.').strip()

        try:
            amount = Decimal(raw)
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, 'Неверная сумма')
            return redirect('wallet')

        # округлим до 2 знаков (копейки)
        amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if amount <= 0:
            messages.error(request, 'Сумма должна быть больше 0')
            return redirect('wallet')

        # лимит пополнения за один раз
        if amount > Decimal('5000'):
            messages.error(request, 'Максимальная сумма пополнения — 5000 ₽')
            return redirect('wallet')

        # (опционально) запрет повару/админу пополнять баланс
        if getattr(request.user, 'role', 'student') != 'student':
            messages.error(request, 'Пополнение доступно только ученикам')
            return redirect('wallet')

        request.user.balance = (request.user.balance or Decimal('0')) + amount
        request.user.save(update_fields=['balance'])

        BalanceTopUp.objects.create(user=request.user, amount=amount)

        messages.success(request, f'Баланс пополнен на {amount} ₽')
        return redirect('wallet')

    topups = BalanceTopUp.objects.filter(user=request.user).order_by('-created_at')[:30]

    return render(request, 'users/wallet.html', {
        'topups': topups
    })


@login_required
def banquet_purchase_view(request):
    """Покупка банкета: выбор готового меню, даты и количества гостей."""
    if getattr(request.user, 'role', 'student') != 'student':
        return HttpResponseForbidden("Доступно только клиенту.")

    menus = BanquetMenu.objects.filter(
        is_active=True,
        status=BanquetMenu.STATUS_APPROVED
    ).prefetch_related('items').order_by('-updated_at')

    selected_menu = None
    guests_count = 10
    event_date = timezone.localdate()

    if request.method == 'POST':
        menu_id = (request.POST.get('menu_id') or '').strip()
        raw_guests = (request.POST.get('guests_count') or '').strip()
        raw_date = (request.POST.get('event_date') or '').strip()

        if menu_id.isdigit():
            selected_menu = menus.filter(id=int(menu_id)).first()

        try:
            guests_count = int(raw_guests)
        except Exception:
            guests_count = 0

        try:
            event_date = timezone.datetime.fromisoformat(raw_date).date() if raw_date else timezone.localdate()
        except Exception:
            event_date = timezone.localdate()

        if not selected_menu:
            messages.error(request, 'Выберите банкетное меню.')
            return redirect('banquets')

        if guests_count <= 0 or guests_count > 500:
            messages.error(request, 'Укажите корректное количество гостей (1–500).')
            return redirect('banquets')

        price_per_person = selected_menu.price_per_person
        total = (Decimal(str(price_per_person)) * Decimal(guests_count)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if (request.user.balance or Decimal('0')) < total:
            messages.error(request, f'Недостаточно средств. Нужно {total} ₽, на балансе {(request.user.balance or Decimal("0"))} ₽')
            return redirect('wallet')

        with transaction.atomic():
            # списываем
            request.user.balance = (request.user.balance or Decimal('0')) - total
            request.user.save(update_fields=['balance'])

            order = Order.objects.create(
                user=request.user,
                total_amount=total,
                status='confirmed',
                order_type='banquet',
                event_date=event_date,
                guests_count=guests_count,
            )

            # каждая позиция — по числу гостей (условно “порции”)
            for item in selected_menu.items.all():
                OrderItem.objects.create(
                    order=order,
                    item=item,
                    quantity=guests_count,
                    price=item.price,
                )

        messages.success(request, f'Банкет оформлен! Сумма: {total} ₽. Дата: {event_date}.')
        return redirect('order_history')

    return render(request, 'users/banquets.html', {
        'menus': menus,
        'selected_menu': selected_menu,
        'guests_count': guests_count,
        'event_date': event_date,
    })

@login_required
def subscription_view(request):
    if getattr(request.user, 'role', 'student') != 'student':
        return redirect('home')

    plans = [
        ('breakfast', 'Завтраки'),
        ('lunch', 'Обеды'),
    ]
    periods = [
        ('week', '1 неделя'),
        ('month', '1 месяц'),
    ]

    prices = {
        ('breakfast', 'week'): Decimal('350'),
        ('breakfast', 'month'): Decimal('1400'),
        ('lunch', 'week'): Decimal('550'),
        ('lunch', 'month'): Decimal('2200'),
    }

    today = timezone.localdate()

    active_subs = (Subscription.objects
                   .filter(user=request.user, start_date__lte=today, end_date__gte=today)
                   .exclude(plan='both')
                   .order_by('-end_date'))

    if request.method == 'POST':
        plan = request.POST.get('plan')
        period = request.POST.get('period')

        if plan not in dict(plans):
            messages.error(request, 'Выберите тариф.')
            return redirect('subscription')

        if period not in dict(periods):
            messages.error(request, 'Выберите период.')
            return redirect('subscription')

        price = prices.get((plan, period))
        if price is None:
            messages.error(request, 'Некорректная комбинация тарифа и периода.')
            return redirect('subscription')

        days = 7 if period == 'week' else 30

        balance = request.user.balance or Decimal('0')
        if balance < price:
            messages.error(request, f'Недостаточно средств. Нужно {price} ₽.')
            return redirect('wallet')

        # если уже есть активный абонемент  — продлеваем именно его
        same_plan_active = active_subs.filter(plan=plan).order_by('-end_date').first()
        if same_plan_active:
            same_plan_active.end_date = same_plan_active.end_date + timedelta(days=days)
            same_plan_active.save(update_fields=['end_date'])

            request.user.balance = balance - price
            request.user.save(update_fields=['balance'])

            messages.success(request, f'Абонемент продлён на {days} дней! До {same_plan_active.end_date}.')
            return redirect('subscription')

        # иначе создаём новый
        new_sub = Subscription.objects.create(
            user=request.user,
            plan=plan,
            start_date=today,
            end_date=today + timedelta(days=days - 1),
        )

        request.user.balance = balance - price
        request.user.save(update_fields=['balance'])

        messages.success(request, f'Абонемент оформлен: {new_sub.get_plan_display()} до {new_sub.end_date}.')
        return redirect('subscription')

    return render(request, 'users/subscription.html', {
        'plans': plans,
        'periods': periods,
        'active_subs': active_subs,
        'today': today,
    })

@login_required
def receive_meal_view(request):
    mark_nav_seen(request, "receive_meal")
    # только ученик
    if getattr(request.user, "role", "student") != "student":
        messages.error(request, "Раздел доступен только ученику.")
        return redirect("menu_list")

    today = timezone.localdate()

    # активные подписки на сегодня
    active_subs = Subscription.objects.filter(
        user=request.user,
        start_date__lte=today,
        end_date__gte=today,
    ).exclude(plan="both")  # если вдруг осталось в БД

    has_breakfast_sub = active_subs.filter(plan="breakfast").exists()
    has_lunch_sub = active_subs.filter(plan="lunch").exists()

    # заявки на сегодня
    breakfast_req = MealRequest.objects.filter(
        user=request.user, date=today, meal_type="breakfast"
    ).order_by("-requested_at").first()

    lunch_req = MealRequest.objects.filter(
        user=request.user, date=today, meal_type="lunch"
    ).order_by("-requested_at").first()

    got_breakfast = MealReceipt.objects.filter(
        user=request.user, date=today, meal_type="breakfast"
    ).exists()

    got_lunch = MealReceipt.objects.filter(
        user=request.user, date=today, meal_type="lunch"
    ).exists()

    history = MealRequest.objects.filter(
        user=request.user,
        status=MealRequest.STATUS_CONFIRMED
    ).order_by('-date', '-confirmed_at', '-requested_at')[:30]

    return render(request, "users/receive_meal.html", {
        "today": today,
        "active_subs": active_subs,
        "has_breakfast_sub": has_breakfast_sub,
        "has_lunch_sub": has_lunch_sub,
        "breakfast_req": breakfast_req,
        "got_breakfast": got_breakfast,
        "got_lunch": got_lunch,
        "lunch_req": lunch_req,
        "history": history,
    })


@login_required
def request_meal(request):
    if getattr(request.user, 'role', 'student') != 'student':
        return HttpResponseForbidden("Доступно только ученику.")
    if request.method != 'POST':
        return redirect('receive_meal')

    meal_type = request.POST.get('meal_type')
    today = timezone.localdate()

    if meal_type not in (MealReceipt.MEAL_BREAKFAST, MealReceipt.MEAL_LUNCH):
        messages.error(request, "Неверный тип питания.")
        return redirect('receive_meal')

    # проверяем абонемент
    sub = Subscription.objects.filter(
        user=request.user,
        plan=meal_type,
        start_date__lte=today,
        end_date__gte=today
    ).first()

    if not sub:
        messages.error(request, "Нет активного абонемента на этот тип питания.")
        return redirect('receive_meal')

    # уже есть активная заявка/выдача/подтверждение на сегодня?
    exists = MealRequest.objects.filter(
        user=request.user, date=today, meal_type=meal_type
    ).exclude(status=MealRequest.STATUS_CANCELLED).exists()

    if exists:
        messages.info(request, "Заявка на сегодня уже создана.")
        return redirect('receive_meal')

    MealRequest.objects.create(
        user=request.user,
        date=today,
        meal_type=meal_type,
        status=MealRequest.STATUS_REQUESTED,
        subscription=sub
    )
    messages.success(request, "Заявка отправлена повару. Ожидайте выдачу.")
    return redirect('receive_meal')


@login_required
def cancel_meal_request(request, request_id):
    if getattr(request.user, 'role', 'student') != 'student':
        return HttpResponseForbidden("Доступно только ученику.")
    if request.method != 'POST':
        return redirect('receive_meal')

    mr = get_object_or_404(MealRequest, id=request_id, user=request.user)
    if mr.status != MealRequest.STATUS_REQUESTED:
        messages.warning(request, "Отменить можно только заявку в статусе 'Запрошено'.")
        return redirect('receive_meal')

    mr.status = MealRequest.STATUS_CANCELLED
    mr.save(update_fields=['status'])
    messages.success(request, "Заявка отменена.")
    return redirect('receive_meal')


@login_required
def confirm_meal(request, request_id):
    if getattr(request.user, 'role', 'student') != 'student':
        return HttpResponseForbidden("Доступно только ученику.")
    if request.method != 'POST':
        return redirect('receive_meal')

    mr = get_object_or_404(MealRequest, id=request_id, user=request.user)

    if mr.status != MealRequest.STATUS_ISSUED:
        messages.warning(request, "Подтвердить можно только после выдачи поваром.")
        return redirect('receive_meal')

    mr.status = MealRequest.STATUS_CONFIRMED
    mr.confirmed_at = timezone.now()
    mr.save(update_fields=['status', 'confirmed_at'])

    # (опционально) фиксируем в MealReceipt для отчётов
    MealReceipt.objects.update_or_create(
        user=mr.user,
        date=mr.date,
        meal_type=mr.meal_type,
        defaults={'issued_by': mr.issued_by}
    )

    messages.success(request, "Получение подтверждено.")
    return redirect('receive_meal')




def get_active_subscription(user):
    today = timezone.localdate()
    return (Subscription.objects
            .filter(user=user, start_date__lte=today, end_date__gte=today)
            .order_by('-end_date')
            .first())

def get_active_subscriptions(user):
    today = timezone.localdate()
    return (Subscription.objects
            .filter(user=user, start_date__lte=today, end_date__gte=today)
            .order_by('-end_date'))


@login_required
def subscription_cancel(request, sub_id: int):
    """Отменить абонемент: ставим end_date = вчера (мягкая отмена)."""
    if getattr(request.user, 'role', 'student') != 'student':
        return HttpResponseForbidden('Доступно только ученику')

    if request.method != 'POST':
        return redirect('subscription')

    sub = get_object_or_404(Subscription, id=sub_id, user=request.user)
    today = timezone.localdate()

    if sub.end_date < today:
        messages.info(request, 'Этот абонемент уже завершён.')
        return redirect('subscription')

    sub.end_date = today - timedelta(days=1)
    sub.save(update_fields=['end_date'])
    messages.success(request, 'Абонемент отменён.')
    return redirect('subscription')

