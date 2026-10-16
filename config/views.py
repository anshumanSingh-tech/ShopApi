"""The public landing page at / (what visitors and the admin's "View site" link open)."""
# ruff: noqa: E501  (long lines are fine inside the HTML/CSS/JS string below)
from django.http import HttpResponse

REPO_URL = "https://github.com/anshumanSingh-tech/ShopApi"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="ShopAPI: an e-commerce backend with oversell-proof checkout and Redis caching.">
<title>ShopAPI - e-commerce backend</title>
<style>
:root{--bg:#fff;--fg:#1c1f24;--muted:#5d6670;--card:#f4f6f8;--line:#dde2e7;--accent:#0b6bcb}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--fg:#e8eaed;--muted:#9aa3ad;--card:#1b1f24;--line:#2b3138;--accent:#5aa9ff}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:48px 20px 64px}
h1{font-size:2rem;margin:0 0 .25rem}
.sub{color:var(--muted);margin:0 0 1.25rem}
.links a{display:inline-block;margin:0 .5rem .5rem 0;padding:.5rem .9rem;border:1px solid var(--line);border-radius:8px;color:var(--fg);text-decoration:none}
.links a.primary{background:var(--accent);border-color:var(--accent);color:#fff}
h2{font-size:1.1rem;margin:2rem 0 .6rem}
ul,ol{padding-left:1.2rem;margin:0}li{margin:.35rem 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin:10px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.card b{display:block}.card span{color:var(--muted);font-size:.9rem}
.bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:.9rem}
button{font:inherit;padding:.4rem .8rem;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
small{color:var(--muted)}
</style>
</head>
<body><main>
<h1>ShopAPI</h1>
<p class="sub">An e-commerce backend: JWT auth, catalog, cart and orders, with a checkout that cannot oversell and a Redis cache in front of reads.</p>
<div class="links">
<a class="primary" href="/api/docs/">API docs (Swagger)</a>
<a href="/api/redoc/">ReDoc</a>
<a href="{{REPO}}">Source on GitHub</a>
</div>

<h2>Try it live</h2>
<div class="bar"><button id="reload">Load products again</button><span id="status">Loading...</span></div>
<div class="grid" id="products"></div>
<small>This calls <code>GET /api/products/</code> from your browser. Reload it and watch <code>X-Cache</code> go from MISS to HIT.</small>

<h2>Try the API in a minute</h2>
<ol>
<li>In the <a href="/api/docs/">docs</a>, run <code>POST /api/auth/register/</code> with your own email, a password and <code>"role": "customer"</code>. Use a throwaway email and password: this is a demo.</li>
<li>Run <code>POST /api/auth/login/</code>, copy the <code>access</code> token, click <b>Authorize</b> and paste it.</li>
<li>Add a product with <code>POST /api/cart/items/</code>, then buy it with <code>POST /api/orders/</code>.</li>
</ol>

<h2>What is inside</h2>
<ul>
<li><b>No overselling:</b> checkout locks product rows, and a test fires 8 simultaneous buyers at 3 items on real PostgreSQL.</li>
<li><b>Redis caching</b> with version-based invalidation; the API keeps working if Redis is down.</li>
<li><b>Roles and ownership:</b> customers, sellers and staff, enforced per object.</li>
<li><b>CI on every push:</b> lint, security checks, tests on PostgreSQL and Redis, Docker build.</li>
<li><b>Stack:</b> Django REST Framework, PostgreSQL (Neon), Redis (Upstash), Docker, Render.</li>
</ul>
<p><small>Hosted on a free plan: after a quiet spell the first request can take about a minute.</small></p>
</main>
<script>
const money = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', maximumFractionDigits: 0});
async function load() {
  const status = document.getElementById('status');
  const box = document.getElementById('products');
  status.textContent = 'Loading...';
  const start = performance.now();
  try {
    const res = await fetch('/api/products/', {headers: {Accept: 'application/json'}});
    const ms = Math.round(performance.now() - start);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    box.replaceChildren(...data.results.slice(0, 6).map((p) => {
      const card = document.createElement('div');
      card.className = 'card';
      const name = document.createElement('b');
      name.textContent = p.name;  // textContent, never innerHTML: names come from sellers
      const meta = document.createElement('span');
      meta.textContent = p.category_name + ' \\u00b7 ' + money.format(Number(p.price)) + ' \\u00b7 ' + p.stock + ' in stock';
      card.append(name, meta);
      return card;
    }));
    status.textContent = 'HTTP ' + res.status + ' \\u00b7 X-Cache: ' + (res.headers.get('X-Cache') || 'n/a') + ' \\u00b7 ' + ms + ' ms \\u00b7 ' + data.count + ' products';
  } catch (err) {
    status.textContent = 'Could not load products (' + err.message + '). The free server may be waking up; try again in a minute.';
  }
}
document.getElementById('reload').addEventListener('click', load);
load();
</script>
</body>
</html>
""".replace("{{REPO}}", REPO_URL)


def home(request):
    return HttpResponse(PAGE)
