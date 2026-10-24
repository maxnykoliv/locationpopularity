from apps.common.testing import BaseAPITestCase

from .models import Category


class CategoryTests(BaseAPITestCase):
    url = "/api/categories/"

    def setUp(self):
        super().setUp()
        self.staff = self.make_user("admin", is_staff=True)
        self.user = self.make_user("alice")

    def test_anyone_can_list(self):
        self.make_category("Museums")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c["name"] for c in response.json()["results"]], ["Museums"])

    def test_only_staff_can_write(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(self.url, {"name": "Cafes"}).status_code, 403)

        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(self.url, {"name": "Cafes"}).status_code, 201)

    def test_category_in_use_cannot_be_deleted(self):
        location = self.make_location(self.user)
        self.client.force_authenticate(self.staff)
        response = self.client.delete(f"{self.url}{location.category_id}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Category.objects.filter(pk=location.category_id).exists())

    def test_unused_category_can_be_deleted(self):
        category = self.make_category("Empty")
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.delete(f"{self.url}{category.pk}/").status_code, 204)
