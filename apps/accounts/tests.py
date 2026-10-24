import re

from django.core import mail
from rest_framework.test import APIClient

from apps.common.testing import BaseAPITestCase, User

PASSWORD = "Str0ng-pass-123"


class RegisterLoginTests(BaseAPITestCase):
    def register(self, **overrides):
        payload = {"username": "alice", "email": "alice@example.com", "password": PASSWORD}
        return self.client.post("/api/auth/register/", payload | overrides, format="json")

    def test_register_logs_the_user_in(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.json())
        self.assertEqual(self.client.get("/api/auth/me/").json()["username"], "alice")

    def test_email_is_unique_case_insensitively(self):
        self.register()
        response = self.register(username="alice2", email="ALICE@Example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    def test_email_is_stored_lowercase(self):
        self.register(email="Alice@Example.COM")
        self.assertEqual(User.objects.get().email, "alice@example.com")

    def test_password_validators_apply(self):
        for password in ("12345678", "short", "password"):
            with self.subTest(password=password):
                self.assertEqual(self.register(password=password).status_code, 400)

    def test_login_logout(self):
        self.make_user("bob")
        response = self.client.post(
            "/api/auth/login/", {"username": "bob", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)

    def test_wrong_password(self):
        self.make_user("bob")
        response = self.client.post(
            "/api/auth/login/", {"username": "bob", "password": "nope"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_csrf_is_enforced_for_session_auth(self):
        user = self.make_user("bob")
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(user)
        self.assertEqual(client.post("/api/auth/logout/").status_code, 403)

        client.get("/api/auth/csrf/")
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code, 204)


class PasswordResetTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user("bob")

    def request_reset(self, email="bob@example.com"):
        return self.client.post("/api/auth/password-reset/", {"email": email}, format="json")

    def reset_params(self):
        body = mail.outbox[-1].body
        uid = re.search(r"uid: (\S+)", body).group(1)
        token = re.search(r"token: (\S+)", body).group(1)
        return uid, token

    def test_full_reset_flow(self):
        self.assertEqual(self.request_reset().status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        uid, token = self.reset_params()

        response = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "new_password": "N3w-secret-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("N3w-secret-pass"))

    def test_token_is_single_use(self):
        self.request_reset()
        uid, token = self.reset_params()
        payload = {"uid": uid, "token": token, "new_password": "N3w-secret-pass"}
        self.client.post("/api/auth/password-reset/confirm/", payload, format="json")
        payload["new_password"] = "An0ther-secret"
        response = self.client.post("/api/auth/password-reset/confirm/", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_unknown_email_gets_the_same_response_and_no_mail(self):
        known = self.request_reset()
        unknown = self.request_reset("nobody@example.com")
        self.assertEqual(known.json(), unknown.json())
        self.assertEqual(len(mail.outbox), 1)

    def test_invalid_token_rejected(self):
        self.request_reset()
        uid, _ = self.reset_params()
        response = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": "bad-token", "new_password": "N3w-secret-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_weak_new_password_rejected(self):
        self.request_reset()
        uid, token = self.reset_params()
        response = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "new_password": "12345678"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json())
