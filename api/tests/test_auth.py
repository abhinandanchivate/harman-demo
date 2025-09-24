"""Tests for authentication endpoints."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Role, UserRole


class UserRegistrationAPITests(APITestCase):
    def setUp(self) -> None:
        self.role = Role.objects.create(name="PATIENT", permissions={})
        self.url = reverse("auth_register")

    def _valid_payload(self) -> dict:
        return {
            "email": "john.doe@example.com",
            "password": "Str0ngPass!",
            "confirm_password": "Str0ngPass!",
            "accept_terms": True,
            "verification_method": "email",
            "profile": {
                "first_name": "John",
                "last_name": "Doe",
                "phone": "+15551234567",
                "date_of_birth": (timezone.now().date() - timedelta(days=12000)).isoformat(),
            },
        }

    def test_successful_registration(self):
        response = self.client.post(self.url, data=self._valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "john.doe@example.com")
        self.assertIn("PATIENT", response.data["roles"])

        user = get_user_model().objects.get(email="john.doe@example.com")
        self.assertTrue(user.check_password("Str0ngPass!"))
        self.assertTrue(UserRole.objects.filter(user=user, role=self.role).exists())

    def test_requires_accepting_terms(self):
        payload = self._valid_payload()
        payload["accept_terms"] = False

        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("accept_terms", response.data)

    def test_password_must_match_confirmation(self):
        payload = self._valid_payload()
        payload["confirm_password"] = "Different1!"

        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_password", response.data)

    def test_password_strength_enforced(self):
        payload = self._valid_payload()
        payload["password"] = "weakpass"
        payload["confirm_password"] = "weakpass"

        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_email_must_be_unique(self):
        self.client.post(self.url, data=self._valid_payload(), format="json")
        response = self.client.post(self.url, data=self._valid_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

