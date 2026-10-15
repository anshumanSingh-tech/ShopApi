import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

def test_http_is_redirected_to_https_but_the_health_check_is_exempt(settings):
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    client = Client()

    redirected = client.get("/api/products/")
    assert redirected.status_code == 301
    assert redirected["Location"].startswith("https://")

    assert client.get("/api/health/").status_code == 200

def test_requests_behind_the_proxy_are_treated_as_https(settings):
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    client = Client()
    res = client.get("/api/products/", HTTP_X_FORWARDED_PROTO="https")
    assert res.status_code == 200

def test_health_endpoint(client):
    res = client.get("/api/health/")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

def test_health_check_works_with_any_host_header_over_plain_http(settings):
    settings.SECURE_SSL_REDIRECT = True
    settings.ALLOWED_HOSTS = ["shopapi-demo.onrender.com"]
    client = Client()

    probe = client.get("/api/health/", HTTP_HOST="10.1.2.3:10000")
    assert probe.status_code == 200
    assert probe.json() == {"status": "ok"}

    assert client.get("/api/products/", HTTP_HOST="10.1.2.3:10000").status_code == 400
