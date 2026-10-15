import threading

import pytest
from django.db import connection

from cart.models import Cart, CartItem
from catalog.models import Category, Product
from orders import services
from orders.exceptions import CheckoutItemsError
from orders.models import Order
from users.models import User

BUYERS = 8
STOCK = 3

pytestmark = pytest.mark.django_db(transaction=True)


def test_concurrent_checkouts_never_oversell():
    if connection.vendor != "postgresql":
        pytest.skip("needs PostgreSQL (SQLite ignores row locks)")

    seller = User.objects.create_user(email="seller@example.com", password="x", role=User.Role.SELLER)
    product = Product.objects.create(
        seller=seller,
        category=Category.objects.create(name="Race"),
        name="Last Item",
        price="100.00",
        stock=STOCK,
    )

    buyers = []
    for i in range(BUYERS):
        user = User.objects.create_user(email=f"buyer{i}@example.com", password="StrongPass123!")
        CartItem.objects.create(cart=Cart.objects.create(user=user), product=product, quantity=1)
        buyers.append(user)

    barrier = threading.Barrier(BUYERS)
    results, lock = [], threading.Lock()

    def worker(user):
        try:
            barrier.wait()
            services.checkout(user, "12 MI Road, Jaipur, Rajasthan 302001")
            outcome = "bought"
        except CheckoutItemsError:
            outcome = "refused"
        except Exception as exc:
            outcome = f"error: {exc!r}"
        finally:
            connection.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(u,)) for u in buyers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("bought") == STOCK, results
    assert results.count("refused") == BUYERS - STOCK, results
    product.refresh_from_db()
    assert product.stock == 0
    assert Order.objects.count() == STOCK
