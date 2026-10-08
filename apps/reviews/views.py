from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.common.permissions import IsOwnerOrAdmin
from apps.locations.models import Location

from .models import Review, ReviewVote
from .querysets import annotate_votes
from .serializers import ReviewSerializer, VoteSerializer

from django.db import transaction
from .services import notify_new_review
from rest_framework.permissions import IsAuthenticated


class ReviewViewSet(viewsets.ModelViewSet):

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]
    filterset_fields = {
        "location": ["exact"],
        "author": ["exact"],
        "rating": ["exact", "gte", "lte"],
    }
    ordering_fields = ["created_at", "rating", "likes"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Review.objects.select_related("author").filter(location__is_deleted=False)
        location_id = self.kwargs.get("location_id")
        if location_id is not None:
            get_object_or_404(Location.objects.all(), pk=location_id)
            qs = qs.filter(location_id=location_id)
        return annotate_votes(qs, self.request.user)

    def create(self, request, *args, **kwargs):
        data = request.data
        location_id = self.kwargs.get("location_id")
        if location_id is not None:
            data = data.copy()
            data["location"] = location_id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        review = serializer.save(author=self.request.user)
        transaction.on_commit(lambda: notify_new_review(review))

    @action(detail=True, methods=["post", "delete"], permission_classes=[IsAuthenticated])
    def vote(self, request, pk=None):
        review = self.get_object()

        if request.method == "DELETE":
            deleted, _ = ReviewVote.objects.filter(review=review, user=request.user).delete()
            if not deleted:
                return Response(
                    {"detail": "Ви ще не голосували за цей відгук."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(status=status.HTTP_204_NO_CONTENT)

        if review.author_id == request.user.id:
            return Response(
                {"detail": "Не можна голосувати за власний відгук."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = VoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data["value"]

        existing = ReviewVote.objects.filter(review=review, user=request.user).first()
        if existing and existing.value == value:
            return Response(
                {"detail": "Ви вже проголосували так само."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ReviewVote.objects.update_or_create(
            review=review, user=request.user, defaults={"value": value}
        )
        fresh = self.get_queryset().get(pk=review.pk)
        return Response(self.get_serializer(fresh).data)