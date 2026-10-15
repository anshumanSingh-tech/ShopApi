import pytest

from users.models import User

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
ME_URL = "/api/auth/me/"

pytestmark = pytest.mark.django_db


def payload(**overrides):
    data = {
        "email": "new@example.com",
        "password": "StrongPass123!",
        "role": "customer",
    }
    data.update(overrides)
    return data


def test_register_creates_user_with_hashed_password(client):
    res = client.post(REGISTER_URL, payload())
    assert res.status_code == 201
    assert "password" not in res.data
    user = User.objects.get(email="new@example.com")
    assert user.password != "StrongPass123!"
    assert user.check_password("StrongPass123!")


def test_register_rejects_duplicate_email_case_insensitive(client, customer):
    res = client.post(REGISTER_URL, payload(email="CUSTOMER@example.com"))
    assert res.status_code == 400
    assert "email" in res.data


def test_register_rejects_weak_password(client):
    res = client.post(REGISTER_URL, payload(password="123"))
    assert res.status_code == 400
    assert "password" in res.data


def test_register_cannot_create_admin_role(client):
    res = client.post(REGISTER_URL, payload(role="admin"))
    assert res.status_code == 400


def test_register_cannot_self_assign_staff(client):
    res = client.post(REGISTER_URL, payload(is_staff=True, is_superuser=True))
    assert res.status_code == 201
    user = User.objects.get(email="new@example.com")
    assert not user.is_staff and not user.is_superuser


def test_login_returns_tokens(client, customer):
    res = client.post(LOGIN_URL, {"email": customer.email, "password": "StrongPass123!"})
    assert res.status_code == 200
    assert {"access", "refresh"} <= set(res.data)


def test_login_wrong_password_rejected(client, customer):
    res = client.post(LOGIN_URL, {"email": customer.email, "password": "wrong"})
    assert res.status_code == 401


def test_me_requires_authentication(client):
    assert client.get(ME_URL).status_code == 401


def test_me_with_jwt_and_cannot_change_role(client, customer):
    token = client.post(LOGIN_URL, {"email": customer.email, "password": "StrongPass123!"}).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    assert client.get(ME_URL).data["email"] == customer.email

    res = client.patch(ME_URL, {"first_name": "Anshuman", "role": "seller"})
    assert res.status_code == 200
    customer.refresh_from_db()
    assert customer.first_name == "Anshuman"
    assert customer.role == "customer"
