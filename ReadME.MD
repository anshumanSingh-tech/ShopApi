# ShopAPI

[![CI](https://github.com/anshumanSingh-tech/ShopApi/actions/workflows/ci.yml/badge.svg)](https://github.com/anshumanSingh-tech/ShopApi/actions/workflows/ci.yml)

**Live demo:** https://shopapi-e1o3.onrender.com · **API docs (Swagger):** https://shopapi-e1o3.onrender.com/api/docs/
_Hosted on a free plan: after a quiet spell the first request can take about a minute while the server wakes up._

An e-commerce backend built with Django REST Framework. Customers browse, add to a cart and check out; sellers manage their own products; staff move orders through their lifecycle. The interesting parts are not the endpoints but how it behaves under load: **checkout cannot oversell stock when buyers collide**, and **reads are served from a Redis cache that is invalidated the moment data changes**.

## At a glance

| | |
|---|---|
| **Correctness under concurrency** | Checkout locks product rows (`SELECT ... FOR UPDATE`). A test fires 8 simultaneous buyers at 3 items on real PostgreSQL: exactly 3 succeed, stock never goes negative. |
| **Performance** | Redis cache: **~4x throughput** (3.8 → 15.0 req/s) and a **94.5% hit ratio** in a 25-user load test (details below). |
| **Quality gates** | 88 tests. Every push runs lint, a deployment security check, the full suite against real PostgreSQL and Redis, and a Docker build. |
| **Deployment** | Render + Neon (PostgreSQL) + Upstash (Redis), all in one region. Deploys only when CI passes. |

## Architecture

```mermaid
flowchart LR
    client["Client or Swagger UI"] -->|HTTPS| app
    subgraph render["Render - Singapore"]
        app["Django REST API<br/>gunicorn + WhiteNoise"]
    end
    app -->|SQL| db[("PostgreSQL<br/>Neon")]
    app -->|"cached reads"| redis[("Redis<br/>Upstash")]
    gh["GitHub Actions<br/>lint, tests, Docker build"] -->|"deploy if checks pass"| render
```

- **Reads** (`GET /products/`, `/categories/`): look in Redis first; on a miss, query PostgreSQL and store the result for 60 seconds. Each response carries an `X-Cache: HIT | MISS | BYPASS` header.
- **Writes** (checkout, product edits): go to PostgreSQL, then bump a single "catalog version" key in Redis after the transaction commits. That makes every cached list and detail page stale at once, without scanning keys.
- **If Redis is down**, requests fall back to the database and log a warning. The cache is an optimisation, never a dependency.

## Try it in 60 seconds

Use a throwaway email and password: this is a public demo.

1. Open the [API docs](https://shopapi-e1o3.onrender.com/api/docs/) and run `POST /api/auth/register/`:
   ```json
   {"email": "you@example.com", "password": "a-long-unique-password", "role": "customer"}
   ```
2. Run `POST /api/auth/login/`, copy the `access` token, click **Authorize** and paste it.
3. `POST /api/cart/items/` with `{"product": 1, "quantity": 2}`, then `POST /api/orders/` with `{"shipping_address": "12 MI Road, Jaipur, Rajasthan"}`.
4. `GET /api/products/1/` again: the stock has dropped by 2. `POST /api/orders/{id}/cancel/` gives it back.

Roles: **customer** (shop), **seller** (also manages their own products), **staff** (manages categories and order status; created by the site owner, not through registration).

## Results: caching under load

Locust, 25 simulated users for 60 s, 966 active products. Django served by waitress (8 threads) on a laptop in Jaipur; Neon and Upstash in Singapore. The same test was run with the cache off and on:

| Endpoint | No cache (p50 / p95) | Redis cache (p50 / p95) |
|---|---|---|
| Product list (pages) | 5.4 s / 6.5 s | 0.23 s / 2.0 s |
| Product list (filters) | 5.3 s / 6.7 s | 0.23 s / 2.2 s |
| Product list (search) | 5.1 s / 7.1 s | 0.23 s / 3.6 s |
| Product detail | 2.7 s / 4.2 s | 0.23 s / 0.78 s |
| Categories | 2.4 s / 4.1 s | 0.23 s / 0.73 s |

**Throughput:** 3.8 → 15.0 req/s (about 4x). **Cache hit ratio:** 94.5%. **Failures:** 0 in both runs.

**How to read this honestly:** the load generator and server were on a different network from the database and cache, so every database or Redis call cost a long round trip. Without the cache each request occupied one of the 8 server threads for about 2 seconds, so requests queued and the latency includes waiting time. The 0.23 s with the cache is two Redis round trips. The throughput figure is the fairer headline than the latency ratio. The p95 with the cache comes from the ~5% of requests that missed while it was filling.

## Problems I hit and how I solved them

1. **Two buyers, one item.** Checking stock and then reducing it is a race. I take row locks in a fixed order (so concurrent checkouts cannot deadlock) and re-validate against the locked rows. I proved the test is meaningful by removing the locks: 8 simultaneous buyers oversold the item and stock reached -1, which a database `CHECK` constraint caught as a second safety net.
2. **Stale cache after checkout.** Checkout updates stock with `queryset.update()`, which sends no Django signals, so signal-based invalidation missed it. Checkout now bumps the cache version explicitly, and always **after** the transaction commits (otherwise another request could re-cache the old data in the gap).
3. **A misleading benchmark.** My first "no cache" numbers were far too slow because Django's `runserver` handles each request in a new thread, which opened a new database connection per request (31 connections for 30 requests, versus 8 with waitress). The first runs also hit an old server that still had caching on. The load test now prints `SERVER CACHE IS ON/OFF` before it starts.
4. **A database on the wrong continent.** My first Neon project was in Ohio, and every query from India cost hundreds of milliseconds. I moved to Singapore and rewrote the seed command from 55 queries to 18.
5. **The platform's health check was rejected.** Django refuses requests whose Host header isn't in `ALLOWED_HOSTS`, and redirects plain HTTP to HTTPS, so a load balancer's probe could mark a healthy service as failed. A small middleware answers `/api/health/` before either check.
6. **"Works on my machine" (Windows vs Linux).** CI failed because Git tracked `Ruff.TOML` while Linux looks for `ruff.toml`, and because the Dockerfile sat in a subfolder. I added a `.gitattributes`, pinned the lint tool version, and now run the same checks locally before pushing.

## Features

- Email-based custom user model with customer / seller / staff roles; JWT access and refresh tokens
- Catalog with categories, search, filtering (price, category, stock), sorting and pagination
- Ownership rules enforced per object: sellers edit only their own products, customers see only their own orders; the owner always comes from the token, never from the request body
- Cart with stock checks; checkout in a single transaction; order status workflow (pending → confirmed → shipped → delivered, or cancelled) with stock returned on cancellation
- Orders store a snapshot of name and price, so history stays correct when products change
- Production settings: HTTPS redirect, secure cookies, HSTS, WhiteNoise static files, structured logging; `manage.py check --deploy` runs in CI

## API overview

| Method | Endpoint | Access |
|---|---|---|
| POST | `/api/auth/register/`, `/login/`, `/refresh/` | public |
| GET / PATCH | `/api/auth/me/` | logged in |
| GET | `/api/products/`, `/api/products/{id}/`, `/api/categories/` | public (cached) |
| POST / PATCH / DELETE | `/api/products/` | seller (own products only) |
| GET | `/api/products/mine/` | seller |
| GET / DELETE | `/api/cart/` | logged in |
| POST / PATCH / DELETE | `/api/cart/items/`, `/api/cart/items/{id}/` | owner of the cart |
| POST / GET | `/api/orders/`, `/api/orders/{id}/` | owner (staff: all) |
| POST | `/api/orders/{id}/cancel/` | owner, while pending |
| PATCH | `/api/orders/{id}/status/` | staff |
| POST / PUT / DELETE | `/api/categories/` | staff |

Product list parameters: `search`, `category`, `category_slug`, `min_price`, `max_price`, `in_stock`, `ordering` (`price`, `-price`, `created_at`, `name`), `page`.

## Tech stack

Python 3.13 · Django 5.2 · Django REST Framework · SimpleJWT · drf-spectacular · PostgreSQL (Neon) · Redis (Upstash) · gunicorn · WhiteNoise · Docker · GitHub Actions · Render · pytest · Locust · ruff

## Run it yourself

```bash
python -m venv venv && source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # then edit .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
With Docker (app + PostgreSQL + Redis): `docker compose up --build`, then open http://localhost:8000.

Without `DATABASE_URL` it uses SQLite; without `REDIS_URL` it uses an in-memory cache. Set `CACHE_ENABLED=False` to turn caching off.

```bash
pytest                    # 86 tests on SQLite; 88 with real PostgreSQL + Redis (as CI runs them)
python manage.py seed_demo_data --products 1000
```
The concurrency test needs PostgreSQL because SQLite ignores row locks:
`TEST_DATABASE_URL=postgresql://user:pass@host:5432/db pytest tests/test_orders_concurrency.py`

### Reproduce the load test
```bash
pip install -r requirements-loadtest.txt
python -m waitress --listen=127.0.0.1:8000 --threads=8 config.wsgi:application   # not runserver
locust -f loadtests/locustfile.py --headless -u 25 -r 5 -t 60s --host http://127.0.0.1:8000 --csv loadtests/results/run
```
Locust prints `SERVER CACHE IS ON/OFF` before it starts. Run once with `CACHE_ENABLED=False` and once with it on, and compare the per-endpoint rows.

## CI and deployment

`.github/workflows/ci.yml` runs on every push: lint (ruff), `manage.py check`, a migrations-are-committed check, `check --deploy` with production settings, the full test suite against PostgreSQL and Redis service containers, then a Docker build with a health-check smoke test. `render.yaml` defines the Render service; it deploys only after the checks pass. Migrations run in the build step because Render's free plan has no shell.

## Known limitations and next steps

- Free hosting sleeps when idle, and the free instance has 0.1 CPU, so absolute latency is modest.
- No rate limiting yet on login and registration, and no email verification.
- Next: rate limiting on the auth endpoints, order-confirmation emails sent from a background job (through an HTTP email API, since Render's free plan blocks SMTP), and a separate production database branch.

## Design decisions

- **Custom user model from day one**: changing it after the first migration is painful.
- **Business logic in `orders/services.py`**, not in views, so it is testable and reusable by background jobs later.
- **Versioned cache keys, not key deletion**: one write invalidates every cached page, with no key scanning.
- **Roles cannot be escalated**: registration only accepts `customer` or `seller`; staff access is granted in Django admin only.