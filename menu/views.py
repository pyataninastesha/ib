import re
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg
from django.utils import timezone
from django.http import JsonResponse, HttpResponseBadRequest
from decimal import Decimal, InvalidOperation
from django.http import HttpResponseForbidden
from django.db import transaction
from core.models import PurchaseRequest
from core.views import mark_nav_seen
from .models import Product, MenuItemIngredient
from django.utils import timezone
from .models import DailyMenu
from .services import has_ingredients
from .models import MenuItem, Category, Review, BanquetReview, Order, OrderItem
from .forms import ReviewForm, BanquetReviewForm, StockAdjustForm
from menu.services import has_recipe, has_ingredients



def _student_only(request):
    if getattr(request.user, 'role', 'student') != 'student':
        return HttpResponseForbidden("Корзина доступна только клиенту.")
    return None

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

def _cart_total_count(cart: dict) -> int:
    total = 0
    for v in (cart or {}).values():
        try:
            total += int(v.get('quantity', 0))
        except Exception:
            continue
    return max(0, total)

@login_required
def update_cart(request, item_id, action):
    forbid = _student_only(request)
    if forbid:
        return forbid

    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')

    action = (action or '').lower()
    if action not in {'increase', 'decrease'}:
        return HttpResponseBadRequest('Unknown action')

    item = get_object_or_404(MenuItem, id=item_id)

    cart = request.session.get('cart', {})
    key = str(item_id)
    entry = cart.get(key, {'quantity': 0, 'price': str(item.price)})
    qty_before = int(entry.get('quantity', 0) or 0)

    if action == 'increase':
        if not has_ingredients(item):
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'Недостаточно ингредиентов',
                    'quantity': qty_before,
                    'cart_count': _cart_total_count(cart),
                },
                status=400
            )
        qty_after = qty_before + 1
        entry['quantity'] = qty_after
        entry.setdefault('price', str(item.price))
        cart[key] = entry

    else:  # decrease
        qty_after = max(0, qty_before - 1)
        if qty_after <= 0:
            cart.pop(key, None)
        else:
            entry['quantity'] = qty_after
            cart[key] = entry

    request.session['cart'] = cart
    return JsonResponse({
        'ok': True,
        'item_id': item_id,
        'quantity': qty_after,
        'cart_count': _cart_total_count(cart),
    })

def ensure_default_menu():
    marker_name = 'Гречка с курицей в томатном соусе'
    if MenuItem.objects.filter(name=marker_name).exists():
        return

    cat_main, _ = Category.objects.get_or_create(
        name='Основные блюда',
        defaults={'description': 'Горячие блюда и основные позиции.', 'order': 1}
    )
    cat_snacks, _ = Category.objects.get_or_create(
        name='Закуски',
        defaults={'description': 'Салаты и лёгкие закуски.', 'order': 2}
    )
    cat_desserts, _ = Category.objects.get_or_create(
        name='Десерты',
        defaults={'description': 'Сладкое к празднику.', 'order': 3}
    )
    cat_drinks, _ = Category.objects.get_or_create(
        name='Напитки',
        defaults={'description': 'Напитки и компоты.', 'order': 4}
    )

    def upsert(name, description, price, category, allergens=''):
        MenuItem.objects.update_or_create(
            name=name,
            defaults={
                'description': description,
                'price': price,
                'category': category,
                'allergens': allergens,
                'is_available': True,
            }
        )
    upsert('Борщ', 'Состав: свёкла, капуста, картофель.', 120, cat_main, 'tomato')
    upsert('Салат Оливье', 'Классический салат для праздника.', 90, cat_snacks, 'eggs')
    upsert('Наполеон', 'Слоёный десерт с кремом.', 110, cat_desserts, 'lactose gluten')
    upsert('Морс', 'Домашний ягодный морс.', 50, cat_drinks, '')


def menu_list(request):
    ensure_default_menu()
    categories = Category.objects.all().order_by('order')
    search_query = (request.GET.get('search') or '').strip()
    section = (request.GET.get('section') or '').strip()  # all | snacks | main | drinks
    selected_allergens = request.GET.getlist('allergen')
    allergen_filter_used = ('allergen_filter' in request.GET) or ('allergen' in request.GET)

    if (not allergen_filter_used) and request.user.is_authenticated and getattr(request.user, "role", "") == "student":
        raw = (getattr(request.user, "avoid_allergens", "") or "").strip()
        if raw:
            selected_allergens = [a.strip() for a in raw.split(",") if a.strip()]

    #  Собираем queryset с нужными связями
    qs = (MenuItem.objects.filter(is_available=True)
          .select_related('category')
          .prefetch_related('ingredients__product'))

    # Фильтр по разделам (удобная навигация как раньше)
    # В seed категории называются: Завтраки / Обеды / Напитки.
    # На витрине: Закуски=Завтраки, Основные блюда=Обеды.
    section_map = {
        'snacks': ['Завтраки'],
        'main': ['Обеды'],
        'drinks': ['Напитки'],
    }
    if section in section_map:
        qs = qs.filter(category__name__in=section_map[section])

    # Исключаем блюда с выбранными аллергенами
    for a in selected_allergens:
        qs = qs.exclude(allergens__contains=a)

    # Поиск
    # В SQLite поиск по кириллице через icontains может быть регистрозависимым.
    # Поэтому для sqlite: фильтруем уже в Python через casefold().
    is_sqlite = 'sqlite3' in settings.DATABASES.get('default', {}).get('ENGINE', '')
    if search_query and (not is_sqlite):
        qs = qs.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))

    # превращаем в список, чтобы дальше не создавать новые queryset-объекты
    items = list(qs)
    if search_query and is_sqlite:
        s = search_query.casefold()
        items = [
            i for i in items
            if s in (getattr(i, 'name', '') or '').casefold()
            or s in (getattr(i, 'description', '') or '').casefold()
        ]

    # Считаем доступность для клиента (для каждого блюда)
    not_available_ids = set()
    for item in items:
        item.client_available = item.is_available and has_ingredients(item, portions=1)
        if not item.client_available:
            not_available_ids.add(item.id)

    # Группируем по категориям
    categories_with_items = []
    for category in categories:
        cat_items = [i for i in items if i.category_id == category.id]
        if cat_items:
            categories_with_items.append((category, cat_items))

    cart = request.session.get('cart', {})
    cart_quantities = {k: int(v.get('quantity', 0)) for k, v in cart.items()}

    return render(request, 'menu/menu_list.html', {
        'categories_with_items': categories_with_items,
        'allergens': MenuItem.ALLERGENS,
        'selected_allergens': selected_allergens,
        'search_query': search_query,
        'section': section,
        'cart_quantities': cart_quantities,
        'not_available_ids': not_available_ids,
    })


@login_required
def item_detail(request, item_id):
    item = get_object_or_404(MenuItem.objects.prefetch_related('ingredients__product'), id=item_id)
    reviews = Review.objects.filter(item=item).select_related('user').order_by('-created_at')
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0

    form = ReviewForm()
    can_order = item.is_available and has_ingredients(item, portions=1)
    return render(request, 'menu/item_detail.html', {
        'item': item,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'form': form,
        'can_order': can_order,
        'allergens': MenuItem.ALLERGENS,
    })


@login_required
def add_review(request, item_id):
    if getattr(request.user, 'role', 'student') != 'student':
        messages.error(request, 'Только клиенты могут оставлять отзывы.')
        return redirect('item_detail', item_id=item_id)

    item = get_object_or_404(MenuItem, id=item_id)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            Review.objects.create(
                user=request.user,
                item=item,
                rating=form.cleaned_data['rating'],
                comment=form.cleaned_data['comment'],
            )
            messages.success(request, 'Отзыв добавлен!')
    return redirect('item_detail', item_id=item_id)


@login_required
def add_to_cart(request, item_id):
    forbid = _student_only(request)
    if forbid:
        return forbid
    item = get_object_or_404(MenuItem, id=item_id)

    if not has_ingredients(item):
        return HttpResponseBadRequest("Недостаточно ингредиентов")

    cart = request.session.get('cart', {})
    entry = cart.get(str(item_id), {'quantity': 0, 'price': str(item.price)})
    entry['quantity'] = int(entry.get('quantity', 0)) + 1
    cart[str(item_id)] = entry
    request.session['cart'] = cart

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
        return JsonResponse({'ok': True, 'item_id': item_id, 'quantity': int(entry['quantity'])})

    return redirect(request.META.get('HTTP_REFERER', 'menu_list'))


@login_required
def remove_from_cart(request, item_id):
    forbid = _student_only(request)
    if forbid:
        return forbid
    cart = request.session.get('cart', {})
    key = str(item_id)
    if key in cart:
        del cart[key]
        request.session['cart'] = cart

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
        return JsonResponse({'ok': True, 'item_id': item_id, 'quantity': 0})

    return redirect(request.META.get('HTTP_REFERER', 'view_cart'))


@login_required
def view_cart(request):
    forbid = _student_only(request)
    if forbid:
        return forbid
    cart = request.session.get('cart', {})
    cart_items = []
    total = Decimal('0')

    for item_id, item_data in cart.items():
        try:
            menu_item = MenuItem.objects.get(id=item_id, is_available=True)
            quantity = int(item_data.get('quantity', 0))

            try:
                price = Decimal(str(item_data.get('price', menu_item.price)))
            except (InvalidOperation, TypeError, ValueError):
                price = Decimal(str(menu_item.price))

            subtotal = price * Decimal(quantity)
            cart_items.append({
                'item': menu_item,
                'quantity': quantity,
                'price': price,
                'subtotal': subtotal
            })
            total += subtotal
        except MenuItem.DoesNotExist:
            continue

    return render(request, 'menu/cart.html', {
        'cart_items': cart_items,
        'total': total,
        'allergens': MenuItem.ALLERGENS,
    })


@login_required
def checkout(request):
    forbid = _student_only(request)
    if forbid:
        return forbid

    if request.method != 'POST':
        return redirect('view_cart')

    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('menu_list')

    # Собираем товары корзины
    cart_lines = []
    total = Decimal('0')

    for item_id, item_data in cart.items():
        try:
            menu_item = MenuItem.objects.get(id=item_id, is_available=True)
        except MenuItem.DoesNotExist:
            continue

        qty = int(item_data.get('quantity', 0))
        if qty <= 0:
            continue

        try:
            price = Decimal(str(item_data.get('price', menu_item.price)))
        except (InvalidOperation, TypeError, ValueError):
            price = Decimal(str(menu_item.price))

        cart_lines.append((menu_item, qty, price))
        total += price * Decimal(qty)

    if not cart_lines:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('menu_list')

    #Проверяем баланс
    if (request.user.balance or Decimal('0')) < total:
        messages.error(request, 'Недостаточно средств на балансе')
        return redirect('wallet')

    # Проверяем наличие продуктов по рецептам
    need_products = {}

    # Подтягиваем все ингредиенты для всех блюд корзины одним запросом
    item_ids = [mi.id for mi, _, _ in cart_lines]
    ings = (
        MenuItemIngredient.objects
        .select_related('product')
        .filter(item_id__in=item_ids)
    )

    # Считаем требуемое кол-во продуктов с учетом количества порций
    qty_map = {mi.id: qty for mi, qty, _ in cart_lines}

    for ing in ings:
        portions = Decimal(qty_map.get(ing.item_id, 0))
        need = Decimal(str(ing.amount)) * portions
        pid = ing.product_id
        need_products[pid] = need_products.get(pid, Decimal('0')) + need

    products = {p.id: p for p in Product.objects.filter(id__in=need_products.keys())}

    not_enough = []
    for pid, need in need_products.items():
        p = products.get(pid)
        if p is None:
            not_enough.append(f"Не найден продукт id={pid}")
            continue
        if Decimal(str(p.stock)) < need:
            not_enough.append(f"{p.name}: нужно {need} {p.unit}, есть {p.stock} {p.unit}")

    if not_enough:
        messages.error(request, "Недостаточно продуктов на складе:\n" + "\n".join(not_enough))
        return redirect('view_cart')

    #создаём заказ и списываем продукты в транзакции
    with transaction.atomic():
        order = Order.objects.create(user=request.user, total_amount=total, status='pending')

        for menu_item, qty, price in cart_lines:
            OrderItem.objects.create(
                order=order,
                item=menu_item,
                quantity=qty,
                price=price
            )

        # списание баланса
        request.user.deduct_from_balance(total)

        # списание продуктов
        for pid, need in need_products.items():
            p = products[pid]
            p.stock = Decimal(str(p.stock)) - need
            p.save(update_fields=['stock'])

    request.session['cart'] = {}
    messages.success(request, f'Заказ #{order.id} успешно оформлен!')
    return redirect('order_history')


@login_required
def order_history(request):
    orders = (Order.objects
              .filter(user=request.user)
              .select_related('banquet_review')
              .prefetch_related('orderitem_set__item')
              .order_by('-created_at'))

    # помечаем "банкет" / "обычный" для шаблона
    for o in orders:
        # основной источник правды — поле order_type
        is_banquet = getattr(o, 'order_type', 'regular') == 'banquet'

        # fallback на старые данные (если поле когда-то не заполнялось)
        if not is_banquet:
            items = list(o.orderitem_set.all())  # already prefetched
            total_qty = sum(i.quantity for i in items)
            unique_count = len(items)
            max_qty = max((i.quantity for i in items), default=0)
            is_banquet = (total_qty >= 10) or (unique_count >= 6) or (max_qty >= 5)

        o.is_banquet = is_banquet
        o.banquet_review_obj = getattr(o, 'banquet_review', None)

    mark_nav_seen(request, "order_history")
    return render(request, 'menu/order_history.html', {'orders': orders})


@login_required
def add_banquet_review(request, order_id):
    forbid = _student_only(request)
    if forbid:
        return forbid

    order = get_object_or_404(Order, id=order_id, user=request.user)

    # отзывы только на проведённые банкеты
    if getattr(order, 'order_type', 'regular') != 'banquet':
        return HttpResponseForbidden("Отзыв доступен только для банкетов.")
    if order.status != 'completed':
        messages.error(request, "Оставить отзыв можно только после проведения банкета.")
        return redirect('order_history')

    if hasattr(order, 'banquet_review'):
        messages.info(request, "Вы уже оставляли отзыв на этот банкет.")
        return redirect('order_history')

    if request.method == 'POST':
        form = BanquetReviewForm(request.POST)
        if form.is_valid():
            review: BanquetReview = form.save(commit=False)
            review.user = request.user
            review.order = order
            review.save()
            messages.success(request, "Спасибо! Отзыв сохранён.")
            return redirect('order_history')
    else:
        form = BanquetReviewForm()

    return render(request, 'menu/banquet_review_form.html', {
        'order': order,
        'form': form,
    })


@login_required
def cancel_order(request, order_id):
    forbid = _student_only(request)
    if forbid:
        return forbid
    if request.method != 'POST':
        return redirect('order_history')

    order = get_object_or_404(Order, id=order_id, user=request.user)
    # Разрешаем отмену только пока заказ не ушёл в "готов/получен"
    if order.status in {'completed', 'ready', 'cancelled'}:
        return redirect('order_history')

    order.status = 'cancelled'
    order.save(update_fields=['status'])
    return redirect('order_history')



def _role_required(role_name):
    def decorator(view_func):
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated or getattr(request.user, "role", None) != role_name:
                return HttpResponseForbidden("Недостаточно прав")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator



@login_required
@_role_required("cook")
def stock_list(request):
    mark_nav_seen(request, "stock_list")
    def _normalize_product_name(value: str) -> str:
        if not value:
            return value
        v = " ".join(value.strip().split())
        while v and v[0] in "([{":
            v = v[1:].lstrip()
        while v and v[-1] in ")]}.;,:!?":
            v = v[:-1].rstrip()
        v = " ".join(v.strip().split())
        v = v.lower()
        return (v[:1].upper() + v[1:]) if v else v

    def _default_min_stock(name: str, unit: str) -> Decimal:
        n = (name or "").lower()
        u = (unit or "г").lower().strip()

        if u == "шт":
            if "яйц" in n:
                return Decimal("20")
            return Decimal("10")

        if u == "мл":
            if "вода" in n or "бульон" in n:
                return Decimal("5000")
            if any(x in n for x in ["молоко", "кефир", "сливк", "сметан", "йогурт"]):
                return Decimal("2000")
            if "масло" in n:
                return Decimal("1000")
            return Decimal("1000")

        if any(x in n for x in ["спец", "перец", "корица", "ванил", "разрыхл", "сода"]):
            return Decimal("100")
        if any(x in n for x in ["соль", "сахар"]):
            return Decimal("1000")
        if any(x in n for x in ["мука", "круп", "рис", "макарон", "вермиш", "лапша", "хлопья", "овсян"]):
            return Decimal("1000")
        if any(x in n for x in ["мяс", "фарш", "куриц", "филе", "рыб"]):
            return Decimal("2000")
        if any(x in n for x in ["сыр", "творог"]):
            return Decimal("500")
        return Decimal("500")

    def _ensure_unit(name: str, current_unit: str) -> str:
        n = (name or "").lower()
        unit = (current_unit or "г").strip()

        piece_keywords = ["яйц", "яблок", "банан", "апельсин", "авокад", "груш", "огур", "помид"]
        if any(k in n for k in piece_keywords):
            return "шт"

        if any(k in n for k in ["вода", "молоко", "кефир", "сок", "сливк", "соус", "масло"]):
            return "мл" if unit != "шт" else unit

        return unit

    # Пункт №12: по кнопке заполняем склад стартовыми остатками,
    # чтобы он не был "пустым" после первого запуска.
    # Делается только по явному действию пользователя (не автоматически).
    if request.method == "POST" and request.POST.get("action") == "seed_stock":
        with transaction.atomic():
            for p in Product.objects.all():
                stock = p.stock or Decimal("0")
                if stock > 0:
                    continue

                # базовое стартовое значение: минимальный остаток (или дефолт, если он ещё не задан)
                min_stock = p.min_stock or Decimal("0")
                if min_stock <= 0:
                    min_stock = _default_min_stock(p.name, p.unit)
                    p.min_stock = min_stock

                p.stock = min_stock
                p.save(update_fields=["stock", "min_stock"])

        messages.success(request, "Склад заполнен стартовыми остатками.")
        return redirect("stock_list")

    with transaction.atomic():
        for p in Product.objects.all():
            norm = _normalize_product_name(p.name)
            if norm and norm != p.name:
                if not Product.objects.exclude(id=p.id).filter(name=norm).exists():
                    p.name = norm
                    p.save(update_fields=["name"])

        products_all = list(Product.objects.all().order_by("id"))
        groups = {}
        for p in products_all:
            key = _normalize_product_name(p.name)
            groups.setdefault(key, []).append(p)

        for key, group in groups.items():
            if not key or len(group) < 2:
                continue

            keeper = group[0]
            for dup in group[1:]:
                # перенос ингредиентов, чтобы рецепты не сломались
                for ing in MenuItemIngredient.objects.filter(product=dup):
                    if MenuItemIngredient.objects.filter(item=ing.item, product=keeper).exists():
                        ing.delete()
                    else:
                        ing.product = keeper
                        ing.save(update_fields=["product"])

                keeper.stock = (keeper.stock or Decimal("0")) + (dup.stock or Decimal("0"))
                keeper.min_stock = max(keeper.min_stock or Decimal("0"), dup.min_stock or Decimal("0"))

                pr = {"шт": 3, "мл": 2, "г": 1}
                if pr.get(dup.unit, 1) > pr.get(keeper.unit, 1):
                    keeper.unit = dup.unit

                dup.delete()
                keeper.save(update_fields=["stock", "min_stock", "unit"])

        # проставляем unit и min_stock
        for p in Product.objects.all():
            changed_fields = []

            new_unit = _ensure_unit(p.name, p.unit)
            if new_unit != p.unit:
                p.unit = new_unit
                changed_fields.append("unit")

            if p.min_stock is None or p.min_stock == 0:
                p.min_stock = _default_min_stock(p.name, p.unit)
                changed_fields.append("min_stock")

            if changed_fields:
                p.save(update_fields=changed_fields)


    # обычный показ страницы
    q = (request.GET.get("q") or "").strip()
    products_qs = Product.objects.all().order_by("name")
    if q:
        products_qs = products_qs.filter(name__iregex=re.escape(q))

    products = []
    for p in products_qs:
        stock = p.stock or Decimal("0")
        min_stock = p.min_stock or Decimal("0")
        p.is_low = (min_stock > 0 and stock < min_stock)  # подсветка, если меньше минимума
        products.append(p)

    return render(request, "cook/stock_list.html", {
        "products": products,
        "q": q,
    })


@login_required
@_role_required("cook")
def stock_fill_to_min(request):
    """Сформировать заявки на закупку: добрать каждый продукт до "максимума".

    В проекте у продукта хранится минимальный остаток (min_stock). Поля "max_stock" нет,
    поэтому в качестве "максимума" берём безопасное и предсказуемое значение: 2 * min_stock.

    Важно: не меняем остатки напрямую ("из ниоткуда").
    Кнопка делает то же, что и выборочное добавление "🛒 В заявку".
    """
    if request.method != "POST":
        return redirect("stock_list")

    def _fmt_qty(d: Decimal) -> str:
        # Убираем лишние нули: 2.0 -> "2", 2.50 -> "2.5"
        s = format(d.normalize(), "f")
        return s.rstrip("0").rstrip(".") if "." in s else s

    created_any = False
    with transaction.atomic():
        for p in Product.objects.all():
            stock = p.stock or Decimal("0")
            min_stock = p.min_stock or Decimal("0")
            if min_stock > 0:
                target = (min_stock * Decimal("2"))
                if stock >= target:
                    continue

                need = (target - stock)
                if need <= 0:
                    continue

                # Если уже есть заявка на этот продукт от этого повара — не дублируем.
                # Важно: кнопка "до максимума" должна сразу формировать заявку администратору,
                # поэтому учитываем как черновики, так и уже отправленные позиции.
                exists = PurchaseRequest.objects.filter(
                    created_by=request.user,
                    title=p.name,
                    status__in=["new", "in_progress"],
                ).exists()
                if exists:
                    continue

                PurchaseRequest.objects.create(
                    created_by=request.user,
                    title=p.name,
                    quantity=_fmt_qty(need),
                    unit=p.unit,
                    # сразу отправляем администратору (как будто нажали "Отправить")
                    status="in_progress",
                )
                created_any = True

    if created_any:
        messages.success(request, "Заявка на закупку отправлена администратору.")
    else:
        messages.info(request, "Склад уже соответствует максимальным остаткам.")

    return redirect("cook_purchase")


@login_required
@_role_required("cook")
def add_to_purchase_request(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        qty = (request.POST.get("quantity") or "").strip()
        if not qty:
            messages.error(request, "Введите количество.")
            return redirect("add_to_purchase_request", product_id=product.id)

        PurchaseRequest.objects.create(
            created_by=request.user,
            title=product.name,
            quantity=qty,
            unit=product.unit,
            status="new"
        )

        messages.success(request, f"{product.name} добавлен в заявку.")
        return redirect("cook_purchase")

    return render(request, "cook/add_to_purchase.html", {"product": product})