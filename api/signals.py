"""Application signals."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance: User, created: bool, **_: dict) -> None:
    """Ensure each user has a profile for RBAC metadata."""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance: User, **_: dict) -> None:
    """Persist related profile when a user is saved."""
    if hasattr(instance, "profile"):
        instance.profile.save()
