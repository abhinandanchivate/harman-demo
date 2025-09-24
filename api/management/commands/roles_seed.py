"""Seed default roles and an initial admin user."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from ...models import Role
from ...rbac import ROLE_PERMISSIONS

User = get_user_model()


class Command(BaseCommand):
    help = "Create default RBAC roles and ensure an admin user exists."

    def add_arguments(self, parser):
        parser.add_argument("--admin-email", dest="admin_email", help="Email for the bootstrap admin user")
        parser.add_argument("--admin-password", dest="admin_password", help="Password for the bootstrap admin user")

    def handle(self, *args, **options):
        for role_name, permissions in ROLE_PERMISSIONS.items():
            role, created = Role.objects.get_or_create(name=role_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created role {role_name}"))
            role.permissions = permissions
            role.save()

        admin_email = options.get("admin_email") or "admin@example.com"
        admin_password = options.get("admin_password") or "ChangeMe123!"
        admin_user, created = User.objects.get_or_create(
            username=admin_email,
            defaults={"email": admin_email, "is_staff": True, "is_superuser": True},
        )
        if created:
            admin_user.set_password(admin_password)
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"Created admin user {admin_email}"))
        else:
            self.stdout.write("Admin user already exists; skipping creation.")

        self.stdout.write(self.style.SUCCESS("Role seeding completed."))
