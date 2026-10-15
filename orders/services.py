from decimal import Decimal

from django.db import transaction
from django.db.models import F

from cart.models import Cart
from catalog.cache import invalidate_on_commit
from catalog.models import Product

from .exceptions import CheckoutItemsError, EmptyCartError, InvalidTransactionError
from .models import Order, OrderItem


S = Order.Status

ALLOWED_TRANSACTIONS = {
    S.PENDING: {S.CONFIRMED, S.CANCELLED},
    S.CONFIRMED: {S.SHIPPED, S.CANCELLED},
    S.SHIPPED: {S.DELIVERED},
    S.DELIVERED: set(),
    S.CANCELLED: set(),
}

@transaction.atomic
def checkout(user, shipping_address):
    cart = Cart.objects.select_for_update().filter(user=user).first()
    if cart is None:
        raise EmptyCartError()
    cart_items = list(cart.items.order_by("product_id"))
    if not cart_items:
        raise EmptyCartError()
    
    products  = {
        p.id: p
        for p in Product.objects.select_for_update()
        .filter(id__in=[i.product_id for i in cart_items])
        .order_by("id")
    }
    
    problems = []
    for item in cart_items:
        p = products[item.product_id]
        if not p.is_active:
            reason = "This product is no longer available."
        elif p.seller_id == user.id:
            reason = "You cannot buy your own product."
        elif p.stock < item.quantity:
            reason = f"Only {p.stock} left in stock."
        else:
            continue
        problems.append(
            {
                "product": p.id,
                "name": p.name,
                "requested": item.quantity,
                "available": p.stock if p.is_active else 0,
                "reason": reason
            }
        )
    if problems:
        raise CheckoutItemsError(problems)
    
    order = Order.objects.create(user=user, shipping_address=shipping_address)
    total = Decimal("0.00")
    order_items = []
    for item in cart_items:
        p = products[item.product_id]
        Product.objects.filter(pk=p.pk).update(stock=F("stock") - item.quantity)
        order_items.append(
            OrderItem(
                order=order,
                product=p,
                seller_id=p.seller_id,
                product_name=p.name,
                unit_price=p.price,
                quantity=item.quantity,
            )
        )
        total += p.price * item.quantity
    OrderItem.objects.bulk_create(order_items)
    invalidate_on_commit()
    
    order.total_amount = total
    order.save(update_fields=["total_amount", "updated_at"])
    cart.items.all().delete()
    return order

def _restock(order):
    items = list(order.items.filter(product_id__isnull=False).order_by("product_id"))
    if not items:
        return 
    list(
        Product.objects.select_for_update()
        .filter(id__in=[i.product_id for i in items])
        .order_by("id")
    )
    for item in items:
        Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
        invalidate_on_commit()
        
@transaction.atomic
def change_status(order_id, new_status, *, allowed_from=None):
    order = Order.objects.select_for_update().get(pk=order_id)
    
    if allowed_from is not None and order.status not in allowed_from:
        raise InvalidTransactionError(
            f"An order that is '{order.status}' can't be changed this way." 
        )
    if new_status not in ALLOWED_TRANSACTIONS[order.status]:
        raise InvalidTransactionError(
            f"Can't move an order from '{order.status}' to '{new_status}'."
        )
        
    if new_status == S.CANCELLED:
        _restock(order)
        
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    return order