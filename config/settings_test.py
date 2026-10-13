import os

os.environ.setdefault("DEBUG", "False")

from .settings import *

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-0123456789")

import dj_database_url

_test_db = os.environ.get("TEST_DATABASE_URL")
DATABASES = {
    "default": dj_database_url.parse(_test_db)
    if _test_db
    else {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]