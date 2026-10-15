import random
import time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils.text import slugify

from catalog.cache import bump_version
from catalog.models import Category, Product
from users.models import User

CATEGORIES = [
    "Handicrafts", "Textiles", "Home Decor", "Jewellery",
    "Pottery", "Furniture", "Kitchenware", "Gifts",
]
ADJECTIVES = ["Handmade", "Classic", "Premium", "Rustic", "Elegant", "Vintage", "Modern", "Artisan"]
MATERIALS = ["Brass", "Cotton", "Clay", "Silver", "Wooden", "Marble", "Silk", "Copper", "Leather"]
NOUNS = ["Vase", "Lamp", "Quilt", "Bowl", "Necklace", "Tray", "Cushion", "Statue", "Bangle", "Mirror"]
SELLER_EMAIL = "demo-seller@example.com"
BATCH_SIZE = 500


class Command(BaseCommand):
    help = "Create demo categories and products for load testing."

    def add_arguments(self, parser):
        parser.add_argument("--products", type=int, default=1000, help="Total demo products wanted")
        parser.add_argument("--reset", action="store_true", help="Delete existing demo products first")

    def handle(self, *args, **opts):
        started = time.monotonic()

        def step(message):
            self.stdout.write(f"[{time.monotonic() - started:6.1f}s] {message}")
            self.stdout.flush()

        total = opts["products"]
        host = connection.settings_dict.get("HOST") or "local file"
        step(f"Database: {connection.vendor} ({host})")
        step("Connecting and looking up the demo seller...")

        with transaction.atomic():
            seller = User.objects.filter(email=SELLER_EMAIL).first()
            if seller is None:
                seller = User.objects.create_user(
                    email=SELLER_EMAIL, password=None, role=User.Role.SELLER
                )
            step("Seller ready. Preparing categories...")

            # two queries for all categories, instead of two per category
            existing = set(Category.objects.filter(name__in=CATEGORIES).values_list("name", flat=True))
            Category.objects.bulk_create(
                [Category(name=n, slug=slugify(n)) for n in CATEGORIES if n not in existing],
                ignore_conflicts=True,
            )
            categories = list(Category.objects.filter(name__in=CATEGORIES))
            if not categories:
                raise CommandError("Could not create or find any demo categories.")

            if opts["reset"]:
                step("Deleting existing demo products...")
                deleted, _ = Product.objects.filter(seller=seller).delete()
                step(f"Deleted {deleted} rows.")

            current = Product.objects.filter(seller=seller).count()
            missing = max(total - current, 0)
            step(f"Demo seller has {current} products; adding {missing}...")

            rng = random.Random(current)  # deterministic, different for each top-up
            products = [
                Product(
                    seller=seller,
                    category=rng.choice(categories),
                    name=f"{rng.choice(ADJECTIVES)} {rng.choice(MATERIALS)} {rng.choice(NOUNS)}",
                    description="Demo product created for load testing.",
                    price=Decimal(rng.randint(99, 9999)),
                    stock=0 if rng.random() < 0.05 else rng.randint(1, 200),
                    is_active=rng.random() > 0.03,
                )
                for _ in range(missing)
            ]
            for start in range(0, len(products), BATCH_SIZE):
                Product.objects.bulk_create(products[start:start + BATCH_SIZE])
                step(f"Saved {min(start + BATCH_SIZE, len(products))} of {len(products)}")

        step("Clearing the catalog cache...")
        bump_version()  # bulk_create sends no signals, so invalidate the cache by hand

        self.stdout.write(self.style.SUCCESS(
            f"Done in {time.monotonic() - started:.1f}s. "
            f"Added {missing} products; demo seller now has {current + missing}."
        ))
