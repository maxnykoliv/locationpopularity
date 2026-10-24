from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.common.permissions import IsAdminOrReadOnly

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ["name"]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete a category that still has locations."},
                status=status.HTTP_409_CONFLICT,
            )
