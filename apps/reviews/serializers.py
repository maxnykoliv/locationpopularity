from django.db import IntegrityError
from rest_framework import serializers

from apps.locations.models import Location

from .models import Review, ReviewVote
from .querysets import annotate_votes


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source="author.username")
    author_id = serializers.ReadOnlyField()
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())
    rating = serializers.IntegerField(min_value=1, max_value=5)

    likes = serializers.IntegerField(read_only=True)
    dislikes = serializers.IntegerField(read_only=True)
    my_vote = serializers.IntegerField(read_only=True)

    class Meta:
        model = Review
        fields = (
            "id", "location", "author", "author_id", "rating", "comment",
            "likes", "dislikes", "my_vote", "created_at", "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
        validators = []

    def validate(self, attrs):
        if self.instance is None:
            user = self.context["request"].user
            if Review.objects.filter(location=attrs["location"], author=user).exists():
                raise serializers.ValidationError(
                    {"detail": "Ви вже залишили відгук до цієї локації."}
                )
        return attrs

    def _fresh(self, instance):
        user = self.context["request"].user
        qs = annotate_votes(Review.objects.select_related("author"), user)
        return qs.get(pk=instance.pk)

    def create(self, validated_data):
        try:
            instance = super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {"detail": "Ви вже залишили відгук до цієї локації."}
            )
        return self._fresh(instance)

    def update(self, instance, validated_data):
        validated_data.pop("location", None)
        return self._fresh(super().update(instance, validated_data))


class VoteSerializer(serializers.Serializer):
    value = serializers.ChoiceField(choices=ReviewVote.VALUE_CHOICES)