import os

os.environ.setdefault("DEBUG", "False")

from .settings import *

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-0123456789")

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]