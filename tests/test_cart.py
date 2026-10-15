import pytest

from cart.models import Cart, CartItem
from catalog.models import Product

CART = "/api/cart/"
ITEMS = "/api/cart/items/"

pytestmark = pytest.mark.django_db


def test_cart_requires_login(client):
    assert client.get(CART).status_code == 401
    assert client.post(ITEMS, {"product": 1, "quantity": 1}).status_code == 401


def test_empty_cart(auth, customer):
    res = auth(customer).get(CART)
    assert res.status_code == 200
    assert res.data["items"] == []
    assert res.data["total"] == "0.00"


def test_add_item_and_totals(auth, customer, product):
    c = auth(customer)
    res = c.post(ITEMS, {"product": product.id, "quantity": 2})
    assert res.status_code == 201
    assert res.data["line_total"] == "998.00"

    cart = c.get(CART).data
    assert cart["item_count"] == 2
    assert cart["total"] == "998.00"


def test_adding_same_product_increases_quantity(auth, customer, product):
    c = auth(customer)
    c.post(ITEMS, {"product": product.id, "quantity": 1})
    c.post(ITEMS, {"product": product.id, "quantity": 2})
    assert CartItem.objects.filter(cart__user=customer).count() == 1
    assert CartItem.objects.get(cart__user=customer).quantity == 3


def test_cannot_add_more_than_stock(auth, customer, product):  # stock is 5
    c = auth(customer)
    assert c.post(ITEMS, {"product": product.id, "quantity": 6}).status_code == 400
    c.post(ITEMS, {"product": product.id, "quantity": 4})
    # 4 already in cart + 2 more = 6 > 5
    assert c.post(ITEMS, {"product": product.id, "quantity": 2}).status_code == 400


def test_cannot_add_inactive_product(auth, customer, product):
    product.is_active = False
    product.save()
    assert auth(customer).post(ITEMS, {"product": product.id, "quantity": 1}).status_code == 400


def test_cannot_add_own_product(auth, seller, product):
    res = auth(seller).post(ITEMS, {"product": product.id, "quantity": 1})
    assert res.status_code == 400
    assert "product" in res.data


@pytest.mark.parametrize("qty", [0, -1, 100])
def test_invalid_quantity_rejected(auth, customer, product, qty):
    assert auth(customer).post(ITEMS, {"product": product.id, "quantity": qty}).status_code == 400


def test_update_quantity(auth, customer, product):
    c = auth(customer)
    item_id = c.post(ITEMS, {"product": product.id, "quantity": 1}).data["id"]
    res = c.patch(f"{ITEMS}{item_id}/", {"quantity": 4})
    assert res.status_code == 200
    assert res.data["quantity"] == 4
    assert c.patch(f"{ITEMS}{item_id}/", {"quantity": 50}).status_code == 400  # over stock
    assert c.patch(f"{ITEMS}{item_id}/", {}).status_code == 400  # quantity required


def test_remove_item_and_clear_cart(auth, customer, product, seller, category):
    other = Product.objects.create(seller=seller, category=category, name="Lamp", price="100", stock=9)
    c = auth(customer)
    first = c.post(ITEMS, {"product": product.id, "quantity": 1}).data["id"]
    c.post(ITEMS, {"product": other.id, "quantity": 1})

    assert c.delete(f"{ITEMS}{first}/").status_code == 204
    assert len(c.get(CART).data["items"]) == 1

    assert c.delete(CART).status_code == 204
    assert c.get(CART).data["items"] == []


def test_cannot_touch_someone_elses_cart_item(auth, customer, product, other_seller):
    from users.models import User

    mine = auth(customer).post(ITEMS, {"product": product.id, "quantity": 1}).data["id"]
    intruder = User.objects.create_user(email="intruder@example.com", password="StrongPass123!")
    c = auth(intruder)
    assert c.patch(f"{ITEMS}{mine}/", {"quantity": 2}).status_code == 404
    assert c.delete(f"{ITEMS}{mine}/").status_code == 404
    assert CartItem.objects.filter(pk=mine).exists()


def test_each_user_has_separate_cart(auth, customer, seller, product):
    auth(customer).post(ITEMS, {"product": product.id, "quantity": 1})
    assert Cart.objects.count() == 1
    assert auth(seller).get(CART).data["items"] == []
