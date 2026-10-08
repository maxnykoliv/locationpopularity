from django.conf import settings
from django.core.cache import cache

from apps.locations.models import LocationView

VIEW_TTL_SECONDS = 60 * 60


def _client_ip(request) -> str:
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _viewer_id(request) -> str:
    if request.user.is_authenticated:
        return f"user:{request.user.pk}"

    session = getattr(request, "session", None)
    if session is not None:
        if not session.session_key:
            session.save()
        if session.session_key:
            return f"session:{session.session_key}"

    return f"ip:{_client_ip(request)}"


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