"""Role based access control helpers."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from .models import UserRole

User = get_user_model()

ROLE_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    "ADMIN": {"*": ["create", "read", "update", "delete", "export", "assign", "manage"]},
    "MANAGER": {
        "patients": ["create", "read", "update", "merge", "export"],
        "observations": ["create", "read", "update", "trend", "alert"],
        "appointments": ["create", "read", "update", "delete"],
        "notifications": ["create", "read", "update"],
        "analytics": ["read"],
        "audit": ["read", "export"],
        "telemedicine": ["create", "read", "update"],
        "hl7": ["create", "read"],
    },
    "STAFF": {
        "patients": ["create", "read", "update"],
        "observations": ["create", "read"],
        "appointments": ["create", "read", "update"],
        "telemedicine": ["read"],
        "notifications": ["create", "read"],
        "hl7": ["read"],
    },
    "PATIENT": {
        "patients": ["create", "read", "update", "export"],
        "appointments": ["create", "read", "update"],
        "telemedicine": ["read"],
        "notifications": ["read"],
    },
    "VIEWER": {"*": ["read"]},
}


def _load_user_roles(user: User) -> Iterable[UserRole]:
    """Return the active role assignments for the user."""
    now = timezone.now()
    return (
        user.role_assignments.filter(effective_date__lte=now)
        .filter(models.Q(expiry_date__isnull=True) | models.Q(expiry_date__gt=now))
        .select_related("role")
    )


def get_user_roles(user: User) -> List[str]:
    """Return the list of active role names for a user."""
    if not user.is_authenticated:
        return []
    if user.is_superuser:
        return ["ADMIN"]
    role_names = {assignment.role.name.upper() for assignment in _load_user_roles(user)}
    if not role_names and user.is_staff:
        role_names.add("MANAGER")
    return sorted(role_names)


def get_permissions_for_role(role_name: str) -> Dict[str, List[str]]:
    """Return the permission mapping for the given role."""
    return ROLE_PERMISSIONS.get(role_name.upper(), {})


def get_permissions_for_user(user: User) -> Dict[str, List[str]]:
    """Aggregate permissions across all of a user's roles."""
    permissions: Dict[str, List[str]] = {}
    for role in get_user_roles(user):
        for entity, actions in get_permissions_for_role(role).items():
            permissions.setdefault(entity, [])
            for action in actions:
                if action not in permissions[entity]:
                    permissions[entity].append(action)
    return permissions


def _matches_entity(entity_permissions: Dict[str, List[str]], entity: str, action: str) -> bool:
    if action in entity_permissions.get("*", []):
        return True
    if action in entity_permissions.get(entity, []):
        return True
    if "*" in entity_permissions and "*" in entity_permissions["*"]:
        return True
    return False


def user_has_permission(user: User, entity: str, action: str, obj: Optional[object] = None) -> bool:
    """Evaluate whether the user has permission for the entity/action combination."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    entity_permissions = get_permissions_for_user(user)
    if _matches_entity(entity_permissions, entity, action):
        return True

    if obj is not None and action in {"read", "update", "delete"}:
        owner = getattr(obj, "created_by", None)
        if owner and owner == user:
            return True
        # Some objects are linked to patients which may have an owner.
        patient = getattr(obj, "patient", None)
        if patient and getattr(patient, "created_by", None) == user:
            return action in {"read", "update"}

    return False


__all__ = [
    "ROLE_PERMISSIONS",
    "get_permissions_for_role",
    "get_permissions_for_user",
    "get_user_roles",
    "user_has_permission",
]
