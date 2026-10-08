import hashlib
from urllib.parse import urlencode

from django.core.cache import cache
from django.db import transaction

LIST_VERSION_KEY = "loc-list-version"
LIST_CACHE_TTL = 60 * 5


def _get_version() -> int:
    cache.add(LIST_VERSION_KEY, 1, timeout=None)  # створить, лише якщо ключа ще немає
    return cache.get(LIST_VERSION_KEY, 1)


def list_cache_key(request) -> str:
    params = urlencode(sorted(request.query_params.lists()), doseq=True)
    digest = hashlib.md5(params.encode()).hexdigest()
    return f"loc-list:v{_get_version()}:{digest}"


def _bump() -> None:
    cache.add(LIST_VERSION_KEY, 1, timeout=None)
    cache.incr(LIST_VERSION_KEY)


def bump_list_version() -> None:
    transaction.on_commit(_bump)