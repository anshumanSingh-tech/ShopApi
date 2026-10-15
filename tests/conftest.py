import pytest
from rest_framework.test import APIClient

from catalog.models import Category, Product
from users.models import User

PASSWORD = "StrongPass123!"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth():
    """Return an API client logged in as the given user."""

    def _auth(user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    return _auth


@pytest.fixture
def customer(db):
    return User.objects.create_user(email="customer@example.com", password=PASSWORD)


@pytest.fixture
def seller(db):
    return User.objects.create_user(email="seller@example.com", password=PASSWORD, role="seller")


@pytest.fixture
def other_seller(db):
    return User.objects.create_user(email="other@example.com", password=PASSWORD, role="seller")


@pytest.fixture
def category(db):
    return Category.objects.create(name="Handicrafts")


@pytest.fixture
def product(seller, category):
    return Product.objects.create(
        seller=seller, category=category, name="Blue Pottery Vase", price="499.00", stock=5
    )


@pytest.fixture
def staff(db):
    return User.objects.create_superuser(email="staff@example.com", password=PASSWORD)
