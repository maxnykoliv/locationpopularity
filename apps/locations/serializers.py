from rest_framework import serializers

from .models import Location


class LocationSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source="author.username")
    author_id = serializers.ReadOnlyField()
    category_name = serializers.ReadOnlyField(source="category.name")

    avg_rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.IntegerField(read_only=True)
    views_7d = serializers.IntegerField(read_only=True)
    popularity = serializers.FloatField(read_only=True)

    class Meta:
        model = Location
        fields = (
            "id", "title", "description", "category", "category_name", "address",
            "latitude", "longitude", "author", "author_id",
            "avg_rating", "reviews_count", "views_7d", "popularity",
            "created_at", "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {
            "latitude": {"coerce_to_string": False},
            "longitude": {"coerce_to_string": False},
        }

    def create(self, validated_data):
        instance = super().create(validated_data)
        return Location.objects.with_stats().select_related("category", "author").get(pk=instance.pk)

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        return Location.objects.with_stats().select_related("category", "author").get(pk=instance.pk)