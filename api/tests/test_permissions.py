"""Tests for RBAC permission helpers."""
from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Patient, Role, UserRole
from ..rbac import get_permissions_for_user, user_has_permission

User = get_user_model()


class PermissionTests(TestCase):
    def setUp(self) -> None:
        self.admin_role = Role.objects.create(name="ADMIN", permissions={"*": ["read"]})
        self.staff_role = Role.objects.create(name="STAFF", permissions={"patients": ["read", "update"]})
        self.admin_user = User.objects.create_user("admin@test.com", password="pass12345")
        self.staff_user = User.objects.create_user("staff@test.com", password="pass12345")
        UserRole.objects.create(user=self.admin_user, role=self.admin_role)
        UserRole.objects.create(user=self.staff_user, role=self.staff_role)
        self.patient = Patient.objects.create(
            resource_id="patient-1",
            primary_identifier="MRN1",
            identifiers=[{"value": "MRN1"}],
            first_name="Test",
            last_name="Patient",
            gender="male",
            birth_date=date(1980, 1, 1),
            created_by=self.staff_user,
        )

    def test_admin_has_global_permissions(self):
        permissions = get_permissions_for_user(self.admin_user)
        self.assertIn("*", permissions)
        self.assertTrue(user_has_permission(self.admin_user, "patients", "delete"))

    def test_staff_can_update_owned_patient(self):
        self.assertTrue(user_has_permission(self.staff_user, "patients", "update", obj=self.patient))

    def test_staff_cannot_delete_without_permission(self):
        self.assertFalse(user_has_permission(self.staff_user, "patients", "delete", obj=self.patient))
