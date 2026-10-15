import pytest

from catalog.models import Category, Product

PRODUCTS = "/api/products/"
CATEGORIES = "/api/categories/"

pytestmark = pytest.mark.django_db


def new_product(category, **overrides):
    data = {
        "name": "Jaipur Quilt",
        "description": "Hand-block printed cotton quilt",
        "price": "1200.00",
        "stock": 10,
        "category": category.id,
    }
    data.update(overrides)
    return data


def test_anyone_can_list_and_view_products(client, product):
    res = client.get(PRODUCTS)
    assert res.status_code == 200
    assert res.data["count"] == 1
    assert client.get(f"{PRODUCTS}{product.id}/").status_code == 200


def test_inactive_products_hidden_from_public(client, product):
    product.is_active = False
    product.save()
    assert client.get(PRODUCTS).data["count"] == 0
    assert client.get(f"{PRODUCTS}{product.id}/").status_code == 404


def test_anonymous_cannot_create_product(client, category):
    assert client.post(PRODUCTS, new_product(category)).status_code == 401


def test_customer_cannot_create_product(auth, customer, category):
    res = auth(customer).post(PRODUCTS, new_product(category))
    assert res.status_code == 403


def test_seller_can_create_product_and_owns_it(auth, seller, category):
    res = auth(seller).post(PRODUCTS, new_product(category, seller_id=999))
    assert res.status_code == 201
    assert Product.objects.get(id=res.data["id"]).seller == seller


@pytest.mark.parametrize("field,value", [("price", "-5"), ("price", "0"), ("stock", "-1")])
def test_invalid_value_rejected(auth, seller, category, field, value):
    res = auth(seller).post(PRODUCTS, new_product(category, **{field: value}))
    assert res.status_code == 400


def test_seller_can_update_own_product(auth, seller, product):
    res = auth(seller).patch(f"{PRODUCTS}{product.id}/", {"stock": 99})
    assert res.status_code == 200
    product.refresh_from_db()
    assert product.stock == 99


def test_seller_cannot_modify_other_product(auth, other_seller, product):
    c = auth(other_seller)
    assert c.patch(f"{PRODUCTS}{product.id}/", {"stock": 0}).status_code == 403
    assert c.delete(f"{PRODUCTS}{product.id}/").status_code == 403


def test_seller_can_delete_own_product(auth, seller, product):
    assert auth(seller).delete(f"{PRODUCTS}{product.id}/").status_code == 204


def test_mine_lists_only_own_products_including_inactive(
    auth, seller, other_seller, category, product
):
    product.is_active = False
    product.save()
    Product.objects.create(seller=other_seller, category=category, name="Other", price="10")
    res = auth(seller).get(f"{PRODUCTS}mine/")
    assert res.status_code == 200
    assert [p["id"] for p in res.data["results"]] == [product.id]


def test_customer_cannot_use_mine(auth, customer):
    assert auth(customer).get(f"{PRODUCTS}mine/").status_code == 403


def test_filter_search_and_ordering(client, seller, category):
    other = Category.objects.create(name="Textiles")
    Product.objects.create(
        seller=seller, category=category, name="Brass Lamp", price="800", stock=3
    )
    Product.objects.create(
        seller=seller, category=category, name="Clay Pot", price="150", stock=0
    )
    Product.objects.create(
        seller=seller, category=other, name="Cotton Quilt", price="2000", stock=7
    )

    assert client.get(PRODUCTS, {"min_price": 500}).data["count"] == 2
    assert client.get(PRODUCTS, {"max_price": 500}).data["count"] == 1
    assert client.get(PRODUCTS, {"category": other.id}).data["count"] == 1
    assert client.get(PRODUCTS, {"category_slug": "textiles"}).data["count"] == 1
    assert client.get(PRODUCTS, {"in_stock": "true"}).data["count"] == 2
    assert client.get(PRODUCTS, {"search": "quilt"}).data["count"] == 1

    prices = [
        p["price"] for p in client.get(PRODUCTS, {"ordering": "price"}).data["results"]
    ]
    assert prices == ["150.00", "800.00", "2000.00"]


def test_pagination_shape(client, seller, category):
    for i in range(25):
        Product.objects.create(seller=seller, category=category, name=f"P{i}", price="10")
    res = client.get(PRODUCTS)
    assert res.data["count"] == 25
    assert len(res.data["results"]) == 20
    assert res.data["next"] is not None


def test_categories_public_read_admin_write(
    client, auth, customer, seller, django_user_model
):
    assert client.get(CATEGORIES).status_code == 200
    assert auth(seller).post(CATEGORIES, {"name": "Toys"}).status_code == 403
    admin = django_user_model.objects.create_superuser(
        email="admin@example.com", password="x"
    )
    res = auth(admin).post(CATEGORIES, {"name": "Home Decor"})
    assert res.status_code == 201
    assert res.data["slug"] == "home-decor"
