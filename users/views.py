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
        return redirect('home')
    if role == 'admin':
        return redirect('home')
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
        return HttpResponseForbidden('Пополнение баланса доступно только клиентам')
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

        # запрет повару/админу пополнять баланс
        if getattr(request.user, 'role', 'student') != 'student':
            messages.error(request, 'Пополнение доступно только клиентам')
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

            # каждая позиция — по числу гостей
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












