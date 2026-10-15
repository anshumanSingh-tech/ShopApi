import os
 
import pytest
from django.core.cache import cache
from django.core.management import call_command
 
from catalog.models import Category, Product
from users.models import User
 
PRODUCTS = "/api/products/"
CATEGORIES = "/api/categories/"
 
pytestmark = pytest.mark.django_db
 
 
@pytest.fixture
def locmem_cache(settings):
    """Turn on a real (in-memory) cache for tests in this file."""
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "tests"}
    }
    cache.clear()
    yield
    cache.clear()
 
 
def x_cache(res):
    return res["X-Cache"]
 
 
# ---------------- hits and misses ----------------
def test_second_identical_request_is_a_hit(client, product, locmem_cache):
    first = client.get(PRODUCTS)
    second = client.get(PRODUCTS)
    assert (x_cache(first), x_cache(second)) == ("MISS", "HIT")
    assert first.json() == second.json()
 
 
def test_detail_is_cached_too(client, product, locmem_cache):
    url = f"{PRODUCTS}{product.id}/"
    assert x_cache(client.get(url)) == "MISS"
    assert x_cache(client.get(url)) == "HIT"
 
 
def test_each_query_string_is_cached_separately(client, product, locmem_cache):
    assert x_cache(client.get(PRODUCTS, {"search": "vase"})) == "MISS"
    assert x_cache(client.get(PRODUCTS, {"search": "vase"})) == "HIT"
    assert x_cache(client.get(PRODUCTS, {"search": "lamp"})) == "MISS"  # different query
 
 
def test_parameter_order_does_not_matter(client, product, locmem_cache):
    client.get(f"{PRODUCTS}?min_price=1&max_price=9999")
    assert x_cache(client.get(f"{PRODUCTS}?max_price=9999&min_price=1")) == "HIT"
 
 
def test_not_found_is_not_cached(client, product, seller, category, locmem_cache):
    """If a 404 were cached, the product would stay 'missing' after it is created."""
    new_id = product.id + 1000
    assert client.get(f"{PRODUCTS}{new_id}/").status_code == 404
    Product.objects.create(id=new_id, seller=seller, category=category, name="Late", price="5", stock=1)
    # (no cache invalidation ran here on purpose: only a cached 404 could still be served)
    assert client.get(f"{PRODUCTS}{new_id}/").status_code == 200
 
 
def test_categories_are_cached(client, category, locmem_cache):
    assert x_cache(client.get(CATEGORIES)) == "MISS"
    assert x_cache(client.get(CATEGORIES)) == "HIT"
 
 
# ---------------- invalidation ----------------
def test_editing_a_product_invalidates(client, product, locmem_cache, django_capture_on_commit_callbacks):
    url = f"{PRODUCTS}{product.id}/"
    client.get(url)
    assert x_cache(client.get(url)) == "HIT"
 
    with django_capture_on_commit_callbacks(execute=True):
        product.name = "Renamed Vase"
        product.save()
 
    res = client.get(url)
    assert x_cache(res) == "MISS"
    assert res.json()["name"] == "Renamed Vase"  # fresh data, not the cached old name
 
 
def test_new_product_appears_in_cached_list(client, product, seller, category, locmem_cache,
                                            django_capture_on_commit_callbacks):
    assert client.get(PRODUCTS).json()["count"] == 1
    assert x_cache(client.get(PRODUCTS)) == "HIT"
 
    with django_capture_on_commit_callbacks(execute=True):
        Product.objects.create(seller=seller, category=category, name="New", price="10", stock=1)
 
    res = client.get(PRODUCTS)
    assert x_cache(res) == "MISS" and res.json()["count"] == 2
 
 
def test_deleting_a_product_invalidates(client, product, locmem_cache, django_capture_on_commit_callbacks):
    url = f"{PRODUCTS}{product.id}/"
    client.get(url)
    assert x_cache(client.get(url)) == "HIT"
    with django_capture_on_commit_callbacks(execute=True):
        product.delete()
    assert client.get(url).status_code == 404
 
 
def test_renaming_a_category_refreshes_product_lists(client, product, category, locmem_cache,
                                                     django_capture_on_commit_callbacks):
    client.get(PRODUCTS)
    with django_capture_on_commit_callbacks(execute=True):
        category.name = "Fine Art"
        category.save()
    assert client.get(PRODUCTS).json()["results"][0]["category_name"] == "Fine Art"
 
 
def test_checkout_stock_change_invalidates(auth, client, customer, product, locmem_cache,
                                           django_capture_on_commit_callbacks):
    """Checkout changes stock with .update() (no signals) - it must bump the cache itself."""
    url = f"{PRODUCTS}{product.id}/"
    assert client.get(url).json()["stock"] == 5
    assert x_cache(client.get(url)) == "HIT"
 
    c = auth(customer)
    c.post("/api/cart/items/", {"product": product.id, "quantity": 2})
    with django_capture_on_commit_callbacks(execute=True):
        res = c.post("/api/orders/", {"shipping_address": "12 MI Road, Jaipur, Rajasthan"})
    assert res.status_code == 201
 
    fresh = client.get(url)
    assert x_cache(fresh) == "MISS" and fresh.json()["stock"] == 3
 
 
def test_cancelling_an_order_invalidates(auth, client, customer, product, locmem_cache,
                                         django_capture_on_commit_callbacks):
    c = auth(customer)
    c.post("/api/cart/items/", {"product": product.id, "quantity": 2})
    with django_capture_on_commit_callbacks(execute=True):
        order_id = c.post("/api/orders/", {"shipping_address": "12 MI Road, Jaipur"}).json()["id"]
    url = f"{PRODUCTS}{product.id}/"
    client.get(url)
    assert x_cache(client.get(url)) == "HIT"
 
    with django_capture_on_commit_callbacks(execute=True):
        c.post(f"/api/orders/{order_id}/cancel/")
    assert client.get(url).json()["stock"] == 5
 
 
# ---------------- who gets cached data ----------------
def test_logged_in_customers_share_the_public_cache(auth, client, customer, product, locmem_cache):
    client.get(PRODUCTS)
    assert x_cache(auth(customer).get(PRODUCTS)) == "HIT"
 
 
def test_sellers_and_staff_bypass_the_cache(auth, seller, staff, product, locmem_cache):
    assert x_cache(auth(seller).get(PRODUCTS)) == "BYPASS"
    assert x_cache(auth(staff).get(PRODUCTS)) == "BYPASS"
 
 
def test_sellers_hidden_products_never_leak_into_public_cache(auth, client, seller, product, locmem_cache):
    product.is_active = False
    product.save()
    assert auth(seller).get(PRODUCTS).json()["count"] == 1  # the seller sees their own hidden product
    public = client.get(PRODUCTS)
    assert public.json()["count"] == 0  # the public must not
    assert client.get(f"{PRODUCTS}{product.id}/").status_code == 404
 
 
def test_writes_are_not_affected_by_caching(auth, seller, category, locmem_cache):
    res = auth(seller).post(
        PRODUCTS, {"name": "Lamp", "price": "50.00", "stock": 2, "category": category.id}
    )
    assert res.status_code == 201
 
 
# ---------------- resilience ----------------
def test_site_keeps_working_when_redis_is_down(client, product, settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://127.0.0.1:1/0",  # nothing is listening here
            "OPTIONS": {"socket_connect_timeout": 1, "socket_timeout": 1},
        }
    }
    res = client.get(PRODUCTS)
    assert res.status_code == 200
    assert res.json()["count"] == 1
    assert x_cache(res) == "BYPASS"
 
 
@pytest.mark.skipif(not os.environ.get("TEST_REDIS_URL"), reason="set TEST_REDIS_URL to test against real Redis")
def test_works_against_real_redis(client, product, settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ["TEST_REDIS_URL"],
            "KEY_PREFIX": "shopapi-test",
        }
    }
    cache.clear()
    try:
        first, second = client.get(PRODUCTS), client.get(PRODUCTS)
        assert (x_cache(first), x_cache(second)) == ("MISS", "HIT")
        assert first.json() == second.json()  # survives a round trip through Redis
    finally:
        cache.clear()
 
 
# ---------------- seed command ----------------
def test_seed_command_creates_products_and_is_repeatable(locmem_cache, django_assert_max_num_queries):
    # every query is a network round trip to a remote database, so keep this small
    with django_assert_max_num_queries(15):
        call_command("seed_demo_data", "--products", "40")
    assert Product.objects.count() == 40
    assert User.objects.get(email="demo-seller@example.com").role == "seller"
    assert Category.objects.count() == 8
 
    call_command("seed_demo_data", "--products", "40")  # no duplicates on re-run
    assert Product.objects.count() == 40
    call_command("seed_demo_data", "--products", "55")
    assert Product.objects.count() == 55
    call_command("seed_demo_data", "--products", "10", "--reset")
    assert Product.objects.count() == 10
 