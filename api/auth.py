"""Authentication helpers built on SimpleJWT."""
from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .rbac import get_permissions_for_user, get_user_roles

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT serializer that includes role metadata."""

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.pk,
            "email": self.user.email,
            "username": self.user.get_username(),
            "roles": get_user_roles(self.user),
            "permissions": get_permissions_for_user(self.user),
        }
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = TokenRefreshSerializer


class MeAPIView(APIView):
    """Return details about the currently authenticated user."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = request.user
        profile = getattr(user, "profile", None)
        data = {
            "id": user.pk,
            "email": user.email,
            "username": user.get_username(),
            "roles": get_user_roles(user),
            "permissions": get_permissions_for_user(user),
        }
        if profile:
            data["profile"] = {
                "phone": profile.phone,
                "date_of_birth": profile.date_of_birth,
                "mfa_enabled": profile.mfa_enabled,
            }
        return Response(data)


__all__ = [
    "CustomTokenObtainPairSerializer",
    "CustomTokenObtainPairView",
    "CustomTokenRefreshView",
    "MeAPIView",
]
