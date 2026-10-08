import django_filters

from .models import Location


class LocationFilter(django_filters.FilterSet):
    min_rating = django_filters.NumberFilter(field_name="avg_rating", lookup_expr="gte")
    max_rating = django_filters.NumberFilter(field_name="avg_rating", lookup_expr="lte")

    class Meta:
        model = Location
        fields = ["category", "author"]
