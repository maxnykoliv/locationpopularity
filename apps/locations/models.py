from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.managers import SoftDeleteManager
from apps.common.models import SoftDeleteModel, TimeStampedModel

from .querysets import LocationQuerySet


class LocationManager(SoftDeleteManager.from_queryset(LocationQuerySet)):
    pass


class Location(TimeStampedModel, SoftDeleteModel):
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        "categories.Category", on_delete=models.PROTECT, related_name="locations"
    )
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="locations"
    )

    objects = LocationManager()
    all_objects = models.Manager.from_queryset(LocationQuerySet)()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class LocationView(models.Model):
    location = models.ForeignKey(
        "Location", on_delete=models.CASCADE, related_name="views"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["location", "viewed_at"], name="locview_loc_viewed_idx"),
            models.Index(fields=["viewed_at"], name="locview_viewed_idx"),
        ]


class Subscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="subscribers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "location"], name="unique_subscription")
        ]