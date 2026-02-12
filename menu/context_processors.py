from decimal import Decimal, InvalidOperation


def cart_summary(request):
    cart = request.session.get('cart', {})

    cart_count = sum(int(v.get('quantity', 0)) for v in cart.values())

    cart_total = Decimal('0')
    for v in cart.values():
        try:
            price = Decimal(str(v.get('price', 0)))
            qty = int(v.get('quantity', 0))
            cart_total += price * Decimal(qty)
        except Exception:
            pass

    return {
        'cart_count': cart_count,
        'cart_total': cart_total,
    }
