import csv
import io
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.testing import BaseAPITestCase
from apps.reviews.models import Review
from config import settings as project_settings

from .models import Location, LocationView, Subscription
from .querysets import VIEWS_WINDOW_DAYS, W_RATING, W_REVIEWS, W_VIEWS

URL = "/api/locations/"
PAYLOAD = {
    "title": "High Castle",
    "description": "Viewpoint over the old town.",
    "address": "Lviv",
    "latitude": 49.848,
    "longitude": 24.039,
}


class LocationCrudTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.category = self.make_category()

    def create(self, **overrides):
        data = PAYLOAD | {"category": self.category.pk} | overrides
        return self.client.post(URL, data, format="json")

    def test_anonymous_can_read_but_not_write(self):
        self.make_location(self.alice)
        self.assertEqual(self.client.get(URL).status_code, 200)
        self.assertEqual(self.create().status_code, 403)

    def test_author_is_the_requesting_user(self):
        self.client.force_authenticate(self.alice)
        response = self.create(author=self.bob.pk)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["author"], "alice")
        self.assertEqual(response.json()["popularity"], 0)

    def test_coordinates_are_validated(self):
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.create(latitude=91).status_code, 400)
        self.assertEqual(self.create(longitude=-181).status_code, 400)

    def test_only_author_or_staff_can_modify(self):
        location = self.make_location(self.alice)
        detail = f"{URL}{location.pk}/"

        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.patch(detail, {"title": "x"}).status_code, 403)
        self.assertEqual(self.client.delete(detail).status_code, 403)

        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.patch(detail, {"title": "Renamed"}).status_code, 200)

        self.client.force_authenticate(self.make_user("admin", is_staff=True))
        self.assertEqual(self.client.patch(detail, {"title": "By staff"}).status_code, 200)

    def test_delete_is_soft(self):
        location = self.make_location(self.alice)
        self.client.force_authenticate(self.alice)

        self.assertEqual(self.client.delete(f"{URL}{location.pk}/").status_code, 204)
        self.assertEqual(self.client.get(f"{URL}{location.pk}/").status_code, 404)
        self.assertEqual(self.client.get(URL).json()["count"], 0)

        stored = Location.all_objects.get(pk=location.pk)
        self.assertTrue(stored.is_deleted)
        self.assertIsNotNone(stored.deleted_at)


class PopularityTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.author = self.make_user("author")
        self.reviewers = [self.make_user(f"r{i}") for i in range(3)]

    def review(self, location, user, rating):
        return Review.objects.create(location=location, author=user, rating=rating)

    def test_score_combines_rating_reviews_and_recent_views(self):
        location = self.make_location(self.author)
        self.review(location, self.reviewers[0], 5)
        self.review(location, self.reviewers[1], 3)
        LocationView.objects.create(location=location)
        LocationView.objects.create(location=location)
        old = LocationView.objects.create(location=location)
        LocationView.objects.filter(pk=old.pk).update(
            viewed_at=timezone.now() - timedelta(days=VIEWS_WINDOW_DAYS + 1)
        )

        body = self.client.get(f"{URL}{location.pk}/").json()
        # the GET above registers one more (recent) view
        self.assertEqual(body["avg_rating"], 4.0)
        self.assertEqual(body["reviews_count"], 2)
        self.assertEqual(body["views_7d"], 3)
        self.assertAlmostEqual(body["popularity"], 4.0 * W_RATING + 2 * W_REVIEWS + 3 * W_VIEWS)

    def test_ordering_and_rating_filter(self):
        top = self.make_location(self.author, title="Top")
        mid = self.make_location(self.author, title="Mid")
        self.make_location(self.author, title="Unrated")
        self.review(top, self.reviewers[0], 5)
        self.review(mid, self.reviewers[0], 3)

        titles = [
            x["title"] for x in self.client.get(f"{URL}?ordering=-popularity").json()["results"]
        ]
        self.assertEqual(titles, ["Top", "Mid", "Unrated"])

        titles = [x["title"] for x in self.client.get(f"{URL}?min_rating=4").json()["results"]]
        self.assertEqual(titles, ["Top"])

    def test_search(self):
        self.make_location(self.author, title="Opera House")
        self.make_location(self.author, title="Market Square", description="Near the opera")
        self.make_location(self.author, title="Park")
        self.assertEqual(self.client.get(f"{URL}?search=opera").json()["count"], 2)


class ViewCountingTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.location = self.make_location(self.make_user("author"))
        self.detail = f"{URL}{self.location.pk}/"

    def views(self):
        return LocationView.objects.filter(location=self.location).count()

    def test_repeat_views_by_same_user_count_once(self):
        self.client.force_authenticate(self.make_user("alice"))
        self.client.get(self.detail)
        self.client.get(self.detail)
        self.assertEqual(self.views(), 1)

    def test_different_users_count_separately(self):
        for name in ("alice", "bob"):
            client = APIClient()
            client.force_authenticate(self.make_user(name))
            client.get(self.detail)
        self.assertEqual(self.views(), 2)

    def test_anonymous_views_are_deduplicated_per_session(self):
        self.client.get(self.detail)
        self.client.get(self.detail)
        APIClient().get(self.detail)
        self.assertEqual(self.views(), 2)

    def test_cleanup_command_removes_old_views(self):
        recent = LocationView.objects.create(location=self.location)
        old = LocationView.objects.create(location=self.location)
        LocationView.objects.filter(pk=old.pk).update(viewed_at=timezone.now() - timedelta(days=30))

        out = StringIO()
        call_command("cleanup_location_views", stdout=out)
        self.assertEqual(list(LocationView.objects.values_list("pk", flat=True)), [recent.pk])
        self.assertIn("Deleted 1", out.getvalue())


class ListCacheTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.location = self.make_location(self.alice)

    def get_list(self, query=""):
        return self.client.get(f"{URL}{query}")

    def test_second_request_is_served_from_cache(self):
        self.assertEqual(self.get_list()["X-Cache"], "MISS")
        self.assertEqual(self.get_list()["X-Cache"], "HIT")

    def test_cache_key_depends_on_query_params(self):
        self.get_list()
        self.assertEqual(self.get_list("?search=park")["X-Cache"], "MISS")
        self.assertEqual(self.get_list("?search=park")["X-Cache"], "HIT")

    def test_writes_invalidate_the_list(self):
        self.get_list()
        with self.captureOnCommitCallbacks(execute=True):
            self.make_location(self.alice, title="New place")
        response = self.get_list()
        self.assertEqual(response["X-Cache"], "MISS")
        self.assertEqual(response.json()["count"], 2)

    def test_new_review_invalidates_the_list(self):
        self.get_list()
        with self.captureOnCommitCallbacks(execute=True):
            Review.objects.create(location=self.location, author=self.make_user("bob"), rating=5)
        self.assertEqual(self.get_list().json()["results"][0]["avg_rating"], 5.0)

    def test_admin_bulk_delete_and_restore_invalidate_the_list(self):
        self.client.force_login(self.make_user("admin", is_staff=True, is_superuser=True))
        changelist = "/admin/locations/location/"
        self.get_list()

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                changelist,
                {
                    "action": "delete_selected",
                    "_selected_action": [self.location.pk],
                    "post": "yes",
                },
            )
        self.assertEqual(self.get_list().json()["count"], 0)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                changelist,
                {"action": "restore_locations", "_selected_action": [self.location.pk]},
            )
        self.assertEqual(self.get_list().json()["count"], 1)

    @override_settings(
        CACHES={
            "default": project_settings.CACHES["default"] | {"LOCATION": "redis://127.0.0.1:1/0"}
        }
    )
    def test_redis_outage_degrades_to_uncached_responses(self):
        with self.assertLogs("django_redis", level="ERROR"):
            self.assertEqual(self.get_list().status_code, 200)
            self.assertEqual(self.client.get(f"{URL}{self.location.pk}/").status_code, 200)


class ExportTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.make_location(self.alice, title='=HYPERLINK("http://evil")', address="-1+1")
        self.make_location(self.alice, title="Safe place")
        self.make_location(self.alice, title="Gone").delete()

    def test_json_export(self):
        response = self.client.get(f"{URL}export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="locations.json"', response["Content-Disposition"])
        titles = sorted(row["title"] for row in response.json())
        self.assertEqual(titles, ['=HYPERLINK("http://evil")', "Safe place"])

    def test_csv_export_neutralizes_formulas(self):
        response = self.client.get(f"{URL}export/?file_format=csv")
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        by_title = {row["title"]: row for row in rows}
        self.assertIn('\'=HYPERLINK("http://evil")', by_title)
        self.assertEqual(by_title['\'=HYPERLINK("http://evil")']["address"], "'-1+1")
        self.assertIn("Safe place", by_title)

    def test_export_respects_filters(self):
        response = self.client.get(f"{URL}export/?search=safe")
        self.assertEqual([row["title"] for row in response.json()], ["Safe place"])

    def test_unsupported_format(self):
        self.assertEqual(self.client.get(f"{URL}export/?file_format=xlsx").status_code, 400)


class SubscriptionTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.location = self.make_location(self.make_user("author"))
        self.url = f"{URL}{self.location.pk}/subscribe/"
        self.user = self.make_user("alice")

    def test_requires_login(self):
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_subscribe_is_idempotent_and_unsubscribe_works(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(self.url).status_code, 201)
        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.assertEqual(Subscription.objects.count(), 1)

        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertFalse(Subscription.objects.exists())
