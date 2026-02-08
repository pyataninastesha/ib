import re
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
from .models import Product, MenuItemIngredient
from django.utils import timezone
from .models import DailyMenu
from .services import has_ingredients
from .models import MenuItem, Category, Review, Order, OrderItem
from .forms import ReviewForm, StockAdjustForm


def _student_only(request):
    if getattr(request.user, 'role', 'student') != 'student':
        return HttpResponseForbidden("Корзина доступна только ученику.")
    return None


def ensure_default_menu():
    marker_name = 'Борщ'
    if MenuItem.objects.filter(name=marker_name).exists():
        return

    cat_breakfast, _ = Category.objects.get_or_create(
        name='Завтраки',
        defaults={'description': '', 'order': 1}
    )
    cat_lunch, _ = Category.objects.get_or_create(
        name='Обеды',
        defaults={'description': '', 'order': 2}
    )
    Category.objects.get_or_create(
        name='Напитки',
        defaults={'description': '', 'order': 3}
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

    # (оставляю как у тебя — если ты уже наполнила блюда, этот блок просто не перезапишет)
    upsert('Борщ', 'Состав: свёкла, капуста, картофель.', 120, cat_lunch, 'tomato')
    upsert('Овсянка на молоке', 'Состав: овсянка, молоко.', 60, cat_breakfast, 'lactose')


def menu_list(request):
    ensure_default_menu()
    categories = Category.objects.all().order_by('order')
    search_query = (request.GET.get('search') or '').strip()
    meal = request.GET.get('meal', 'all')
    selected_allergens = request.GET.getlist('allergen')
    allergen_filter_used = ('allergen_filter' in request.GET) or ('allergen' in request.GET)
    if (not allergen_filter_used) and request.user.is_authenticated and getattr(request.user, "role", "") == "student":
        raw = (getattr(request.user, "avoid_allergens", "") or "").strip()
        if raw:
            selected_allergens = [a.strip() for a in raw.split(",") if a.strip()]

    items = MenuItem.objects.filter(is_available=True)

    # исключаем блюда с выбранными аллергенами
    for a in selected_allergens:
        items = items.exclude(allergens__contains=a)

    if meal in ('breakfast', 'lunch', 'drinks'):
        meal_map = {'breakfast': 'Завтраки', 'lunch': 'Обеды', 'drinks': 'Напитки'}
        items = items.filter(category__name=meal_map[meal])

    if search_query:
        items = items.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))

    categories_with_items = []
    for category in categories:
        cat_items = items.filter(category=category)
        if cat_items.exists():
            categories_with_items.append((category, cat_items))

    cart = request.session.get('cart', {})
    cart_quantities = {k: int(v.get('quantity', 0)) for k, v in cart.items()}
    today = timezone.localdate()
    daily_menu = DailyMenu.objects.filter(date=today).prefetch_related(
        "breakfast_items__ingredients__product",
        "lunch_items__ingredients__product",
    ).first()

    not_available_ids = set()
    for item in items:
        if not has_ingredients(item):
            not_available_ids.add(item.id)

    return render(request, 'menu/menu_list.html', {
        'categories_with_items': categories_with_items,
        'allergens': MenuItem.ALLERGENS,
        'selected_allergens': selected_allergens,
        'search_query': search_query,
        'meal': meal,
        'cart_quantities': cart_quantities,
        'today': today,
        'daily_menu': daily_menu,
        'not_available_ids': not_available_ids,
    })


@login_required
def item_detail(request, item_id):
    item = get_object_or_404(MenuItem.objects.prefetch_related('ingredients__product'), id=item_id)
    reviews = Review.objects.filter(item=item).select_related('user').order_by('-created_at')
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0

    form = ReviewForm()
    can_order = has_ingredients(item)
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
        messages.error(request, 'Только ученики могут оставлять отзывы.')
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
def cart_increase(request, item_id):
    forbid = _student_only(request)
    if forbid:
        return forbid
    cart = request.session.get('cart', {})
    key = str(item_id)

    if key not in cart:
        item = get_object_or_404(MenuItem, id=item_id)
        cart[key] = {'quantity': 1, 'price': str(item.price)}
    else:
        cart[key]['quantity'] = int(cart[key].get('quantity', 0)) + 1

    request.session['cart'] = cart
    qty = int(cart[key]['quantity'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
        return JsonResponse({'ok': True, 'item_id': item_id, 'quantity': qty})

    return redirect(request.META.get('HTTP_REFERER', 'menu_list'))


@login_required
def cart_decrease(request, item_id):
    forbid = _student_only(request)
    if forbid:
        return forbid
    cart = request.session.get('cart', {})
    key = str(item_id)

    if key not in cart:
        qty = 0
    else:
        qty = int(cart[key].get('quantity', 0)) - 1
        if qty <= 0:
            del cart[key]
            qty = 0
        else:
            cart[key]['quantity'] = qty

    request.session['cart'] = cart

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
        return JsonResponse({'ok': True, 'item_id': item_id, 'quantity': qty})

    return redirect(request.META.get('HTTP_REFERER', 'menu_list'))


@login_required
def checkout(request):
    forbid = _student_only(request)
    if forbid:
        return forbid

    # ✅ только POST (кнопкой из корзины)
    if request.method != 'POST':
        return redirect('view_cart')

    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('menu_list')

    # 1) Собираем товары корзины
    cart_lines = []  # [(MenuItem, qty, price)]
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

    # 2) Проверяем баланс
    if (request.user.balance or Decimal('0')) < total:
        messages.error(request, 'Недостаточно средств на балансе')
        return redirect('wallet')

    # 3) Проверяем наличие продуктов по рецептам
    # need_products[product_id] = Decimal(total_amount_needed)
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

    # Если у блюда нет ингредиентов — считаем, что это допустимо (можно включить строгий режим при желании)
    # Строгий режим: если у блюда нет ингредиентов, запретить оформление.

    # Загружаем продукты и проверяем остатки
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

    # 4) Всё ок — создаём заказ и списываем продукты в транзакции
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
    orders = Order.objects.filter(user=request.user).prefetch_related('orderitem_set__item').order_by('-created_at')
    return render(request, 'menu/order_history.html', {'orders': orders})


@login_required
def mark_received(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if request.method != 'POST':
        return redirect('order_history')

    if order.status != 'ready':
        messages.warning(request, 'Отметить получение можно только когда заказ "Готов к выдаче".')
        return redirect('order_history')

    order.status = 'completed'
    order.received_by_student = True
    order.received_at = timezone.now()
    order.save(update_fields=['status', 'received_by_student', 'received_at', 'updated_at'])

    messages.success(request, f'Заказ #{order.id} отмечен как полученный.')
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

        # 3) проставляем unit и min_stock только если они ещё пустые
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
    org = getattr(request.user, 'organization', None)
    if org:
        products_qs = products_qs.filter(organization=org)
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
def stock_adjust(request, product_id, action):
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        form = StockAdjustForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]

            if action == "add":
                product.stock = (product.stock or Decimal("0")) + amount
                product.save(update_fields=["stock"])
                messages.success(request, f"Пополнено: {product.name} +{amount} {product.unit}")
            elif action == "remove":
                product.stock = (product.stock or Decimal("0")) - amount
                if product.stock < 0:
                    product.stock = Decimal("0")
                product.save(update_fields=["stock"])
                messages.success(request, f"Списано: {product.name} -{amount} {product.unit}")
            else:
                messages.error(request, "Неверное действие")

            return redirect("stock_list")
    else:
        form = StockAdjustForm()

    return render(request, "cook/stock_adjust.html", {
        "product": product,
        "action": action,
        "form": form,
    })

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
            organization=getattr(request.user, 'organization', None),
            title=product.name,       # ✅ вместо product=...
            quantity=qty,             # у тебя quantity строка/текст — так безопаснее
            unit=product.unit,
            status="new"              # ✅ черновик
        )

        messages.success(request, f"{product.name} добавлен в заявку.")
        return redirect("cook_purchase")

    return render(request, "cook/add_to_purchase.html", {"product": product})