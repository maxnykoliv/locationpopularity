from datetime import timedelta

from django.db.models import (
    Avg, Count, ExpressionWrapper, F, FloatField, IntegerField, OuterRef, Subquery, Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.common.managers import SoftDeleteQuerySet

W_RATING = 10.0
W_REVIEWS = 2.0
W_VIEWS = 0.5
VIEWS_WINDOW_DAYS = 7


class LocationQuerySet(SoftDeleteQuerySet):
    def with_stats(self):
        from .models import LocationView

        since = timezone.now() - timedelta(days=VIEWS_WINDOW_DAYS)
        views_sq = (
            LocationView.objects.filter(location=OuterRef("pk"), viewed_at__gte=since)
            .order_by()
            .values("location")
            .annotate(c=Count("pk"))
            .values("c")
        )
        return self.annotate(
            avg_rating=Coalesce(Avg("reviews__rating"), Value(0.0), output_field=FloatField()),
            reviews_count=Count("reviews", distinct=True),
            views_7d=Coalesce(Subquery(views_sq, output_field=IntegerField()), Value(0)),
        ).annotate(
            popularity=ExpressionWrapper(
                F("avg_rating") * W_RATING + F("reviews_count") * W_REVIEWS + F("views_7d") * W_VIEWS,
                output_field=FloatField(),
            )
        )