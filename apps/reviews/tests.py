from django.core import mail

from apps.common.testing import BaseAPITestCase
from apps.locations.models import Subscription

from .models import Review


class ReviewTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_user("owner")
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.location = self.make_location(self.owner)
        self.nested = f"/api/locations/{self.location.pk}/reviews/"

    def post_review(self, user, **data):
        self.client.force_authenticate(user)
        return self.client.post(self.nested, {"rating": 4} | data, format="json")

    def test_create_through_nested_route(self):
        response = self.post_review(self.alice, rating=5, comment="Great view")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(
            (body["author"], body["rating"], body["location"]), ("alice", 5, self.location.pk)
        )
        self.assertEqual((body["likes"], body["dislikes"], body["my_vote"]), (0, 0, None))

    def test_one_review_per_user_and_location(self):
        self.post_review(self.alice)
        response = self.post_review(self.alice, rating=1)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Review.objects.count(), 1)

    def test_rating_must_be_between_1_and_5(self):
        for rating in (0, 6):
            with self.subTest(rating=rating):
                self.assertEqual(self.post_review(self.alice, rating=rating).status_code, 400)

    def test_location_cannot_be_changed_on_update(self):
        review_id = self.post_review(self.alice).json()["id"]
        other = self.make_location(self.owner, title="Other")
        response = self.client.patch(
            f"/api/reviews/{review_id}/", {"location": other.pk, "rating": 2}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["location"], self.location.pk)

    def test_only_author_can_edit(self):
        review_id = self.post_review(self.alice).json()["id"]
        self.client.force_authenticate(self.bob)
        self.assertEqual(
            self.client.patch(f"/api/reviews/{review_id}/", {"rating": 1}).status_code, 403
        )

    def test_reviews_of_deleted_locations_are_hidden(self):
        self.post_review(self.alice)
        self.location.delete()
        self.assertEqual(self.client.get("/api/reviews/").json()["count"], 0)
        self.assertEqual(self.client.get(self.nested).status_code, 404)
        self.assertEqual(self.post_review(self.bob).status_code, 404)

    def test_filter_by_rating(self):
        self.post_review(self.alice, rating=5)
        self.post_review(self.bob, rating=2)
        response = self.client.get("/api/reviews/?rating__gte=4")
        self.assertEqual([r["author"] for r in response.json()["results"]], ["alice"])


class VoteTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        location = self.make_location(self.make_user("owner"))
        self.review = Review.objects.create(location=location, author=self.alice, rating=5)
        self.url = f"/api/reviews/{self.review.pk}/vote/"

    def vote(self, value):
        return self.client.post(self.url, {"value": value}, format="json")

    def test_cannot_vote_on_own_review(self):
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.vote(1).status_code, 403)

    def test_like_switch_and_retract(self):
        self.client.force_authenticate(self.bob)

        body = self.vote(1).json()
        self.assertEqual((body["likes"], body["dislikes"], body["my_vote"]), (1, 0, 1))
        self.assertEqual(self.vote(1).status_code, 400)

        body = self.vote(-1).json()
        self.assertEqual((body["likes"], body["dislikes"], body["my_vote"]), (0, 1, -1))

        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertEqual(self.client.delete(self.url).status_code, 404)

    def test_invalid_value(self):
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.vote(2).status_code, 400)

    def test_order_by_likes(self):
        second = Review.objects.create(
            location=self.make_location(self.alice, title="Other"), author=self.bob, rating=3
        )
        self.client.force_authenticate(self.make_user("carol"))
        self.client.post(f"/api/reviews/{second.pk}/vote/", {"value": 1}, format="json")
        response = self.client.get("/api/reviews/?ordering=-likes")
        self.assertEqual(response.json()["results"][0]["id"], second.pk)


class NotificationTests(BaseAPITestCase):
    def test_location_author_and_subscribers_are_notified(self):
        owner = self.make_user("owner")
        subscriber = self.make_user("sub")
        self.make_user("bystander")
        no_email = self.make_user("noemail", email="")
        reviewer = self.make_user("reviewer")
        location = self.make_location(owner, title="Opera")
        Subscription.objects.create(user=subscriber, location=location)
        Subscription.objects.create(user=no_email, location=location)
        # the reviewer is subscribed too, but shouldn't be told about their own review
        Subscription.objects.create(user=reviewer, location=location)

        self.client.force_authenticate(reviewer)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                f"/api/locations/{location.pk}/reviews/",
                {"rating": 5, "comment": "Wonderful"},
                format="json",
            )

        recipients = sorted(address for message in mail.outbox for address in message.to)
        self.assertEqual(recipients, ["owner@example.com", "sub@example.com"])
        self.assertIn("Opera", mail.outbox[0].subject)
        self.assertIn("Wonderful", mail.outbox[0].body)
