from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.common.permissions import IsOwnerOrAdmin

from .filters import LocationFilter
from .models import Location, Subscription
from .serializers import LocationSerializer
from .services.views_counter import register_view

from django.core.cache import cache
from .services.cache import LIST_CACHE_TTL, bump_list_version, list_cache_key

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from .services.export import SUPPORTED_FORMATS, export_response

class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]
    filterset_class = LocationFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "avg_rating", "popularity"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Location.objects.with_stats().select_related("category", "author")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if register_view(instance, request):
            instance = self.get_queryset().get(pk=instance.pk)
        return Response(self.get_serializer(instance).data)

    def list(self, request, *args, **kwargs):
        key = list_cache_key(request)
        cached = cache.get(key)
        if cached is not None:
            response = Response(cached)
            response["X-Cache"] = "HIT"
            return response

        response = super().list(request, *args, **kwargs)
        cache.set(key, response.data, LIST_CACHE_TTL)
        response["X-Cache"] = "MISS"
        return response

    def perform_destroy(self, instance):
        instance.delete()
        bump_list_version()

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        file_format = request.query_params.get("file_format", "json").lower()
        if file_format not in SUPPORTED_FORMATS:
            return Response(
                {"file_format": f"Підтримуються: {', '.join(SUPPORTED_FORMATS)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = self.filter_queryset(self.get_queryset())
        return export_response(queryset, file_format)

    @action(detail=True, methods=["post", "delete"], permission_classes=[IsAuthenticated])
    def subscribe(self, request, pk=None):
        location = self.get_object()
        if request.method == "POST":
            _, created = Subscription.objects.get_or_create(user=request.user, location=location)
            return Response({"subscribed": True}, status=201 if created else 200)
        Subscription.objects.filter(user=request.user, location=location).delete()
        return Response(status=204)