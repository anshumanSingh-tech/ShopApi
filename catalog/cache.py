import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework.response import Response

logger = logging.getLogger(__name__)

VERSION_KEY = "catalog:version"

def get_version():
    try:
        return cache.get(VERSION_KEY, "0")
    except Exception as exc:
        logger.warning("Cache unavailable, serving from database: %s", exc)
        return None

def build_key(request):
    version = get_version()
    if version is None:
        return None
    params = sorted((k, sorted(v)) for k, v in request.query_params.lists())
    digest = hashlib.sha256(f"{request.path}|{params}".encode()).hexdigest()[:32]
    return f"catalog:{version}:{digest}"

def cache_get(key):
    try:
        return cache.get(key)
    except Exception as exc:
        logger.warning("Cache read failed: %s", exc)
        return None


def cache_set(key, value, ttl):
    try:
        cache.set(key, value, ttl)
    except Exception as exc:
        logger.warning("Cache write failed: %s", exc)

def bump_version():
    try:
        cache.set(VERSION_KEY, str(time.time_ns()), timeout=None)
    except Exception as exc:
        logger.warning("Cache invalidation failed (enteries expire by TTL): %s", exc)

def invalidate_on_commit():
    transaction.on_commit(bump_version)

class CachedReadMixin:
    cache_ttl = None

    def _can_use_cache(self, request):
        user = request.user
        return not (user.is_authenticated and (user.is_staff or user.is_seller))

    @staticmethod
    def _tag(response, status):
        response["X-Cache"] = status
        return response

    def _cached_response(self, request, producer, *args, **kwargs):
        if not self._can_use_cache(request):
            return self._tag(producer(*args, **kwargs), "BYPASS")

        key = build_key(request)
        if key is None:
            return self._tag(producer(*args, **kwargs), "BYPASS")

        data = cache_get(key)
        if data is not None:
            return self._tag(Response(data), "HIT")

        response = producer(*args, **kwargs)
        if response.status_code == 200:
            ttl = self.cache_ttl or settings.CATALOG_CACHE_TTL
            cache_set(key, response.data, ttl)
        return self._tag(response, "MISS")

    def list(self, request, *args, **kwargs):
        return self._cached_response(request, super().list, request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return self._cached_response(request, super().retrieve, request, *args, **kwargs)
