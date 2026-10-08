from django.core.cache import cache

from apps.locations.models import LocationView

VIEW_TTL_SECONDS = 60 * 60  # один перегляд на годину


def _viewer_id(request) -> str:
    if request.user.is_authenticated:
        return f"user:{request.user.pk}"
    return f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def register_view(location, request) -> bool:
    key = f"loc-view:{location.pk}:{_viewer_id(request)}"
    if not cache.add(key, 1, timeout=VIEW_TTL_SECONDS):
        return False
    try:
        LocationView.objects.create(
            location=location,
            user=request.user if request.user.is_authenticated else None,
        )
    except Exception:
        cache.delete(key)
        raise
    return True