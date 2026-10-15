import os

os.environ.setdefault("DEBUG", "False")

from .settings import *  # noqa: F403, F401

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-0123456789")

import dj_database_url

_test_db = os.environ.get("TEST_DATABASE_URL")
DATABASES = {
    "default": dj_database_url.parse(_test_db)
    if _test_db
    else {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
CATALOG_CACHE_TTL = 60

SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = None
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
