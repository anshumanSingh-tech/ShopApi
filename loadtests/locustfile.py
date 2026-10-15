import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests
from locust import HttpUser, between, events, task

cache_status = Counter()  # HIT / MISS / BYPASS counts across all simulated users

SEARCH_TERMS = ["lamp", "vase", "quilt", "brass", "silk", "bowl", "marble"]
FILTERS = [
    {"min_price": 500, "max_price": 3000},
    {"ordering": "price"},
    {"ordering": "-price"},
    {"in_stock": "true", "ordering": "-created_at"},
    {"category_slug": "pottery"},
    {"category_slug": "textiles", "ordering": "price"},
]


class Shopper(HttpUser):
    wait_time = between(0.5, 1.5)  # a real person pauses between clicks
    product_ids = []  # filled in once by discover_products() below


    def _get(self, url, name, params=None):
        with self.client.get(url, params=params, name=name, catch_response=True) as res:
            if res.status_code == 200:
                cache_status[res.headers.get("X-Cache", "none")] += 1
                res.success()
            else:
                res.failure(f"HTTP {res.status_code}")

    @task(5)
    def browse_listing(self):
        # most people look at the first pages
        page = random.choices([1, 2, 3, 4, 5], weights=[50, 25, 12, 8, 5])[0]
        self._get("/api/products/", "GET /products/ [page]", {"page": page})

    @task(3)
    def filter_or_sort(self):
        self._get("/api/products/", "GET /products/ [filter]", random.choice(FILTERS))

    @task(2)
    def search(self):
        self._get("/api/products/", "GET /products/ [search]", {"search": random.choice(SEARCH_TERMS)})

    @task(4)
    def view_product(self):
        if not Shopper.product_ids:
            return
        # a few popular products get most of the views
        pool = Shopper.product_ids[:5] if random.random() < 0.7 else Shopper.product_ids
        product_id = random.choice(pool)
        # The name below is a PLAIN string on purpose (not an f-string): Locust groups
        # every product id under this one label in the results table.
        self._get(f"/api/products/{product_id}/", "GET /products/{id}/")

    @task(1)
    def categories(self):
        self._get("/api/categories/", "GET /categories/")


@events.test_start.add_listener
def prepare_test(environment, **kwargs):
    """
    Runs once before the timer starts, so none of this is part of the results:
      1. fetch real product ids for the detail pages
      2. tell you whether the server's cache is ON or OFF
      3. warm up the server (open its database connections)
    """
    host = environment.host
    try:
        res = requests.get(f"{host}/api/products/", timeout=180)
        res.raise_for_status()
        Shopper.product_ids = [p["id"] for p in res.json()["results"]]

        again = requests.get(f"{host}/api/products/", timeout=180)
        mode = "ON" if again.headers.get("X-Cache") == "HIT" else "OFF"
        print("\n" + "=" * 60)
        print(f"  SERVER CACHE IS {mode}")
        print("  A 'before' run must say OFF. An 'after' run must say ON.")
        print("=" * 60)

        # distinct search terms -> every request misses and hits the database,
        # which opens each server thread's database connection up front
        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(
                lambda i: requests.get(f"{host}/api/products/", params={"search": f"warmup{i}"}, timeout=60),
                range(16),
            ))
        print(f"Warm-up done, {len(Shopper.product_ids)} product ids found. Starting the test...\n")
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: could not prepare the test against {host}: {exc}")


@events.test_stop.add_listener
def print_cache_summary(environment, **kwargs):
    total = sum(cache_status.values())
    if not total:
        return
    hits = cache_status["HIT"]
    print("\n--- Cache summary ---")
    for status, n in cache_status.most_common():
        print(f"{status:>7}: {n:>6}  ({n / total:.1%})")
    print(f"Hit ratio: {hits / total:.1%} of {total} successful responses")
