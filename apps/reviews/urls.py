from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ReviewViewSet

router = DefaultRouter()
router.register("reviews", ReviewViewSet, basename="review")

urlpatterns = router.urls + [
    path(
        "locations/<int:location_id>/reviews/",
        ReviewViewSet.as_view({"get": "list", "post": "create"}),
        name="location-reviews",
    ),
]