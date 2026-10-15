from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core ---------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY")  # required: app refuses to start without it
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

# Render sets this automatically (e.g. shopapi.onrender.com), so no manual host setup is needed.
RENDER_EXTERNAL_HOSTNAME = config("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# --- Applications -------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    # Local
    "users",
    "catalog",
    "cart",
    "orders",
]

MIDDLEWARE = [
    "config.middleware.HealthCheckMiddleware",  # must stay first: answers the health probe
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static files, must be right after Security
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database -----------------------------------------------------------
# Uses DATABASE_URL (Neon Postgres) when set, otherwise local SQLite.
DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=60,
        conn_health_checks=True,  # Neon suspends idle compute; reconnect safely
    )
}
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    # Without this a bad network makes commands hang forever. With it they fail
    # after 10 seconds with a clear error message instead.
    DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 10

# --- Auth ---------------------------------------------------------------
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Django REST Framework ---------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ShopAPI",
    "DESCRIPTION": "E-commerce backend built with Django REST Framework.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Cache --------------------------------------------------------------
# REDIS_URL set      -> Redis (Upstash in production)
# REDIS_URL not set  -> in-process memory cache (fine for local development)
# CACHE_ENABLED=False-> no caching at all (used for the "before" load test)
CACHE_ENABLED = config("CACHE_ENABLED", default=True, cast=bool)
REDIS_URL = config("REDIS_URL", default="")
CATALOG_CACHE_TTL = config("CATALOG_CACHE_TTL", default=60, cast=int)  # seconds

if not CACHE_ENABLED:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
elif REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "shopapi",
            # Fail fast instead of hanging a request when Redis is unreachable
            "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2},
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# --- Internationalisation ----------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# --- Static files -------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # hashed + compressed file names in production; plain storage while developing
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# --- Production security --------------------------------------------------
# Only active when DEBUG is off. Render terminates HTTPS in front of the app and
# tells us the original scheme through the X-Forwarded-Proto header.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Start with a short HSTS lifetime; raise it once you are sure HTTPS is permanent.
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=3600, cast=int)
    # includeSubDomains / preload make no sense on a shared *.onrender.com domain
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]

# --- Logging (Render shows whatever is written to stdout) ----------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": config("LOG_LEVEL", default="INFO")},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
