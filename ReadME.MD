# ShopAPI

An e-commerce backend built with Django and Django REST Framework.

**Status:** Phases 1-3 complete (auth, catalog, cart, orders with safe stock handling, Redis caching, load testing). Background jobs, CI and deployment are coming in later phases.

## Stack
Django 5.2 · DRF · SimpleJWT · drf-spectacular (Swagger) · PostgreSQL (Neon) · Redis (Upstash) · pytest · Locust

## Features so far
- Email-based custom user model with `customer` / `seller` roles
- JWT authentication (register, login, refresh, profile)
- Product catalog with categories
- Search, filtering (price, category, stock), sorting and pagination
- Role- and ownership-based permissions (sellers manage only their own products)
- Shopping cart (add, change quantity, remove, clear) with stock checks
- Checkout that turns a cart into an order inside a single database transaction
- **Oversell protection:** product rows are locked (`SELECT ... FOR UPDATE`) during checkout, so two buyers can never both get the last item; a database `CHECK` constraint is the second safety net
- Order status workflow (pending → confirmed → shipped → delivered, or cancelled) with stock returned on cancellation
- Orders keep a snapshot of name and price, so history stays correct when products change
- **Redis caching** of public product/category reads with instant, version-based invalidation; the site keeps working if Redis goes down
- Load-test suite (Locust) and a seeding command to generate realistic data
- Interactive API docs at `/api/docs/`

## Run locally
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                               # then edit .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Open http://127.0.0.1:8000/api/docs/

## Run tests
```bash
pytest
```
The concurrency test (`tests/test_orders_concurrency.py`) needs PostgreSQL because SQLite ignores row locks, so it is skipped by default. To run it against a Postgres database:
```bash
TEST_DATABASE_URL=postgresql://user:pass@host:5432/dbname pytest tests/test_orders_concurrency.py
```

## Caching
Public `GET /api/products/`, `/api/products/{id}/` and `/api/categories/` are cached for 60 seconds (`CATALOG_CACHE_TTL`). Each response carries an `X-Cache` header: `HIT`, `MISS` or `BYPASS` (sellers and staff always see live data).

- **Invalidation:** every cache key includes a "catalog version". Editing or deleting a product or category (or any stock change from checkout/cancel) sets a new version after the database transaction commits, which makes all old entries unreachable at once.
- **Safe by design:** only the public view is cached, so a seller's hidden products can never leak. If Redis is unreachable, requests are served from the database and a warning is logged.
- **Config:** set `REDIS_URL` to use Redis, leave it unset for an in-memory cache, or set `CACHE_ENABLED=False` to disable caching.

## Load testing
```bash
pip install -r requirements-loadtest.txt
python manage.py seed_demo_data --products 1000
mkdir loadtests/results
```
**Start the server with waitress, not `runserver`.** `runserver` handles every request in a brand-new thread, so every request opens a new database connection (a TLS handshake and login each time). With a remote database that cost swamps everything else and exaggerates the benefit of caching. Waitress reuses its threads and therefore its connections, like a real production server:
```bash
# Terminal 1  (set CACHE_ENABLED=False in .env for the "before" run, True for "after")
python -m waitress --listen=127.0.0.1:8000 --threads=8 config.wsgi:application

# Terminal 2 - 25 simulated shoppers for 60 seconds
locust -f loadtests/locustfile.py --headless -u 25 -r 5 -t 60s --host http://127.0.0.1:8000 --csv loadtests/results/before
```
Before the timer starts, Locust prints `SERVER CACHE IS ON` or `OFF`. A "before" run must say OFF (and finish with `Hit ratio: 0.0%`), an "after" run must say ON. If not, an old server is probably still running; stop it first (check with `netstat -ano | findstr :8000`).

Repeat with caching enabled and `--csv loadtests/results/after`. Compare the per-endpoint rows (not the "Aggregated" row) and record them below.

| Endpoint | No cache (p50 / p95) | Redis cache (p50 / p95) | p50 improvement |
|---|---|---|---|
| Product list (pages) | 5.4 s / 6.5 s | 0.23 s / 2.0 s | 23x |
| Product list (filters) | 5.3 s / 6.7 s | 0.23 s / 2.2 s | 23x |
| Product list (search) | 5.1 s / 7.1 s | 0.23 s / 3.6 s | 22x |
| Product detail | 2.7 s / 4.2 s | 0.23 s / 0.78 s | 12x |
| Categories | 2.4 s / 4.1 s | 0.23 s / 0.73 s | 10x |

**Throughput:** 3.8 req/s without the cache, 15.0 req/s with it (about 4x). **Cache hit ratio:** 94.5%. **Failures:** 0 in both runs.

_Test setup:_ Locust 2.46, 25 simulated users (0.5-1.5 s think time) for 60 s, 966 active products. Django served by waitress (8 threads) on a laptop in Jaipur, India; Neon PostgreSQL and Upstash Redis both in AWS Singapore.

_How to read these numbers:_ the server, database and cache were on different networks, so every database or Redis call costs a long round trip. Without the cache, each request kept one of the 8 server threads busy for about 2 seconds, so requests queued and the latency includes waiting time; the 0.23 s with the cache is two Redis round trips. The p95 with the cache (0.7-3.6 s) comes from the ~5% of requests that missed the cache while it was still filling. These will be re-measured against the deployed app (server, database and cache in the same region) in a later phase.

## API overview
| Method | Endpoint | Access |
|---|---|---|
| POST | `/api/auth/register/` | public |
| POST | `/api/auth/login/` | public |
| POST | `/api/auth/refresh/` | public |
| GET/PATCH | `/api/auth/me/` | logged in |
| GET | `/api/products/` | public |
| POST | `/api/products/` | seller |
| PUT/PATCH/DELETE | `/api/products/{id}/` | owning seller |
| GET | `/api/products/mine/` | seller |
| GET | `/api/cart/` | logged in |
| DELETE | `/api/cart/` | logged in (empties cart) |
| POST | `/api/cart/items/` | logged in |
| PATCH/DELETE | `/api/cart/items/{id}/` | owner of the cart |
| POST | `/api/orders/` | logged in (checkout) |
| GET | `/api/orders/`, `/api/orders/{id}/` | own orders (staff: all) |
| POST | `/api/orders/{id}/cancel/` | owner, while pending |
| PATCH | `/api/orders/{id}/status/` | staff |
| GET | `/api/categories/` | public |
| POST/PUT/DELETE | `/api/categories/` | admin |

Product list query params: `search`, `category`, `category_slug`, `min_price`, `max_price`, `in_stock`, `ordering` (`price`, `-price`, `created_at`, `name`), `page`.

## Design decisions
(To be expanded as the project grows.)
- **Custom user model from day one** - changing it after the first migration is painful.
- **Owner comes from the JWT, not the request body** - a seller can't create products as someone else.
- **Row locking at checkout** - validating stock and then decrementing it is a race condition unless the rows are locked first. Locks are taken in ascending product id order so concurrent checkouts can't deadlock.
- **All-or-nothing checkout** - if any item is unavailable, nothing is bought, no stock changes and the cart is kept.
- **Order items are snapshots** - name and price are copied at purchase time.
- **Business logic lives in `orders/services.py`**, not in views, so it can be tested and reused (e.g. by background jobs later).
- **Cache invalidation by version, not by key deletion** - one write invalidates every cached list and detail; no key scanning.
- **Invalidate after commit** - bumping the version inside the transaction would let another request re-cache the old data before the commit lands.
- **Cache failures never break requests** - Redis is an optimisation, not a dependency.
- **Roles can't be escalated** - registration only accepts `customer`/`seller`; admin access is granted only via Django admin.