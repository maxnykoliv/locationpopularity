from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.categories.models import Category
from apps.locations.models import Location

LOCMEM_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

User = get_user_model()


@override_settings(CACHES=LOCMEM_CACHE)
class BaseAPITestCase(APITestCase):
    """API test case with an isolated in-memory cache and a few factories."""

    def setUp(self):
        super().setUp()
        cache.clear()

    @staticmethod
    def make_user(username, **extra):
        extra.setdefault("email", f"{username}@example.com")
        return User.objects.create_user(username=username, password="Str0ng-pass-123", **extra)

    @staticmethod
    def make_category(name="Parks"):
        return Category.objects.get_or_create(name=name)[0]

    def make_location(self, author, **extra):
        data = {
            "title": "Stryiskyi Park",
            "description": "A large park in Lviv.",
            "category": extra.pop("category", None) or self.make_category(),
            "address": "Lviv",
            "latitude": Decimal("49.823"),
            "longitude": Decimal("24.022"),
            "author": author,
        }
        return Location.objects.create(**(data | extra))
