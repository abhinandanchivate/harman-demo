"""Custom DRF permission classes for RBAC enforcement."""
from __future__ import annotations

from typing import Dict, Tuple

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .rbac import get_user_roles, user_has_permission


class IsAdmin(BasePermission):
    """Allow only ADMIN role users."""

    message = "You must be an admin to perform this action."

    def has_permission(self, request, view) -> bool:
        return "ADMIN" in get_user_roles(request.user)


class IsManagerOrReadOnly(BasePermission):
    """Managers have full access; others read-only."""

    message = "Write access is restricted to managers."

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return "MANAGER" in get_user_roles(request.user) or "ADMIN" in get_user_roles(request.user)


def HasEntityPermission(entity: str, action: str) -> type:
    """Return a permission class verifying the given entity/action combination."""

    class _HasEntityPermission(BasePermission):
        message = "You do not have permission to perform this action."

        def has_permission(self, request, view) -> bool:
            return user_has_permission(request.user, entity, action)

        def has_object_permission(self, request, view, obj) -> bool:
            return user_has_permission(request.user, entity, action, obj=obj)

    _HasEntityPermission.__name__ = f"HasPermission_{entity}_{action}"
    return _HasEntityPermission


class ActionPermissionMixin:
    """Mixin to map viewset actions to RBAC requirements."""

    action_permission_map: Dict[str, Tuple[str, str]] = {}

    def get_permissions(self):  # type: ignore[override]
        permissions = super().get_permissions()  # type: ignore[misc]
        entity_action = self.action_permission_map.get(getattr(self, "action", ""))
        if entity_action:
            entity, action = entity_action
            permissions.append(HasEntityPermission(entity, action)())
        return permissions


__all__ = [
    "ActionPermissionMixin",
    "HasEntityPermission",
    "IsAdmin",
    "IsManagerOrReadOnly",
]
