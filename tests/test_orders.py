import pytest

from catalog.models import Product
from orders.models import Order
from users.models import User

CART_ITEMS = "/api/cart/items/"
CART = "/api/cart/"
ORDERS = "/api/orders/"
ADDRESS = "12 MI Road, Jaipur, Rajasthan 302001"


@pytest.fixture
def lamp(seller, category):
    return Product.objects.create(
        seller=seller, category=category, name="Brass Lamp", price="800.00", stock=3
    )


def fill_cart(c, *pairs):
    for product, qty in pairs:
        assert c.post(CART_ITEMS, {"product": product.id, "quantity": qty}).status_code == 201


def place_order(c):
    return c.post(ORDERS, {"shipping_address": ADDRESS})


# ---------------- checkout ----------------
def test_checkout_creates_order_reduces_stock_and_clears_cart(auth, customer, product, lamp):
    c = auth(customer)
    fill_cart(c, (product, 2), (lamp, 1))  # 2*499 + 800 = 1798

    res = place_order(c)
    assert res.status_code == 201
    assert res.data["status"] == "pending"
    assert res.data["total_amount"] == "1798.00"
    assert len(res.data["items"]) == 2

    product.refresh_from_db()
    lamp.refresh_from_db()
    assert (product.stock, lamp.stock) == (3, 2)
    assert c.get(CART).data["items"] == []


def test_order_keeps_price_snapshot_after_product_changes(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    order_id = place_order(c).data["id"]

    product.price = "9999.00"
    product.name = "Renamed"
    product.save()

    item = c.get(f"{ORDERS}{order_id}/").data["items"][0]
    assert item["unit_price"] == "499.00"
    assert item["product_name"] == "Blue Pottery Vase"


def test_order_survives_product_deletion(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    order_id = place_order(c).data["id"]
    product.delete()
    res = c.get(f"{ORDERS}{order_id}/")
    assert res.status_code == 200
    assert res.data["items"][0]["product_name"] == "Blue Pottery Vase"


def test_checkout_empty_cart_fails(auth, customer):
    res = place_order(auth(customer))
    assert res.status_code == 400
    assert Order.objects.count() == 0


def test_checkout_requires_valid_address(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    assert c.post(ORDERS, {"shipping_address": "short"}).status_code == 400
    assert c.post(ORDERS, {}).status_code == 400


def test_checkout_fails_atomically_when_one_item_is_short(auth, customer, product, lamp):
    """If any item can't be bought, nothing is bought: no order, no stock change."""
    c = auth(customer)
    fill_cart(c, (product, 2), (lamp, 3))
    Product.objects.filter(pk=lamp.pk).update(stock=1)  # someone else bought lamps meanwhile

    res = place_order(c)
    assert res.status_code == 400
    assert res.data["items"][0]["product"] == lamp.id
    assert res.data["items"][0]["available"] == 1

    product.refresh_from_db()
    assert product.stock == 5  # untouched, even though it was fine on its own
    assert Order.objects.count() == 0
    assert len(c.get(CART).data["items"]) == 2  # cart kept so the user can fix it


def test_checkout_rejects_product_deactivated_after_adding(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    Product.objects.filter(pk=product.pk).update(is_active=False)
    res = place_order(c)
    assert res.status_code == 400
    assert Order.objects.count() == 0


def test_checkout_requires_login(client):
    assert client.post(ORDERS, {"shipping_address": ADDRESS}).status_code == 401


def test_buying_the_last_items_leaves_zero_stock(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 5))
    assert place_order(c).status_code == 201
    product.refresh_from_db()
    assert product.stock == 0


# ---------------- visibility ----------------
def test_users_only_see_their_own_orders(auth, customer, seller, product, lamp):
    c = auth(customer)
    fill_cart(c, (product, 1))
    order_id = place_order(c).data["id"]

    other = User.objects.create_user(email="other.buyer@example.com", password="StrongPass123!")
    oc = auth(other)
    fill_cart(oc, (lamp, 1))
    place_order(oc)

    mine = c.get(ORDERS).data
    assert mine["count"] == 1 and mine["results"][0]["id"] == order_id
    assert oc.get(f"{ORDERS}{order_id}/").status_code == 404  # not even revealed to exist


def test_staff_sees_all_orders(auth, customer, staff, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    place_order(c)
    assert auth(staff).get(ORDERS).data["count"] == 1


def test_orders_filter_by_status(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    place_order(c)
    assert c.get(ORDERS, {"status": "pending"}).data["count"] == 1
    assert c.get(ORDERS, {"status": "shipped"}).data["count"] == 0


# ---------------- cancelling ----------------
def test_customer_can_cancel_pending_order_and_stock_returns(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 3))
    order_id = place_order(c).data["id"]
    product.refresh_from_db()
    assert product.stock == 2

    res = c.post(f"{ORDERS}{order_id}/cancel/")
    assert res.status_code == 200
    assert res.data["status"] == "cancelled"
    product.refresh_from_db()
    assert product.stock == 5


def test_cancelling_twice_does_not_restock_twice(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 3))
    order_id = place_order(c).data["id"]
    assert c.post(f"{ORDERS}{order_id}/cancel/").status_code == 200
    assert c.post(f"{ORDERS}{order_id}/cancel/").status_code == 409
    product.refresh_from_db()
    assert product.stock == 5


def test_customer_cannot_cancel_after_confirmation(auth, customer, staff, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    order_id = place_order(c).data["id"]
    auth(staff).patch(f"{ORDERS}{order_id}/status/", {"status": "confirmed"})
    assert c.post(f"{ORDERS}{order_id}/cancel/").status_code == 409


def test_cannot_cancel_someone_elses_order(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    order_id = place_order(c).data["id"]
    other = User.objects.create_user(email="x@example.com", password="StrongPass123!")
    assert auth(other).post(f"{ORDERS}{order_id}/cancel/").status_code == 404


# ---------------- staff status changes ----------------
def test_status_endpoint_is_staff_only(auth, customer, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    order_id = place_order(c).data["id"]
    res = c.patch(f"{ORDERS}{order_id}/status/", {"status": "confirmed"})
    assert res.status_code == 403


def test_full_happy_path_status_flow(auth, customer, staff, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    order_id = place_order(c).data["id"]
    s = auth(staff)
    for status in ["confirmed", "shipped", "delivered"]:
        res = s.patch(f"{ORDERS}{order_id}/status/", {"status": status})
        assert res.status_code == 200 and res.data["status"] == status


@pytest.mark.parametrize(
    "path",
    [
        ["shipped"],  # can't skip confirmation
        ["delivered"],
        ["confirmed", "pending"],  # can't go backwards
        ["confirmed", "shipped", "delivered", "cancelled"],  # delivered is final
    ],
)
def test_invalid_status_transitions_rejected(auth, customer, staff, product, path):
    c = auth(customer)
    fill_cart(c, (product, 1))
    order_id = place_order(c).data["id"]
    s = auth(staff)
    for status in path[:-1]:
        assert s.patch(f"{ORDERS}{order_id}/status/", {"status": status}).status_code == 200
    assert s.patch(f"{ORDERS}{order_id}/status/", {"status": path[-1]}).status_code == 409


def test_staff_cancel_of_confirmed_order_restocks(auth, customer, staff, product):
    c = auth(customer)
    fill_cart(c, (product, 4))
    order_id = place_order(c).data["id"]
    s = auth(staff)
    s.patch(f"{ORDERS}{order_id}/status/", {"status": "confirmed"})
    assert s.patch(f"{ORDERS}{order_id}/status/", {"status": "cancelled"}).status_code == 200
    product.refresh_from_db()
    assert product.stock == 5


def test_unknown_status_value_rejected(auth, customer, staff, product):
    c = auth(customer)
    fill_cart(c, (product, 1))
    order_id = place_order(c).data["id"]
    assert auth(staff).patch(f"{ORDERS}{order_id}/status/", {"status": "teleported"}).status_code == 400
