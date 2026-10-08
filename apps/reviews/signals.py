from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.locations.services.cache import bump_list_version

from .models import Review


@receiver([post_save, post_delete], sender=Review)
def invalidate_on_review_change(sender, **kwargs):
    bump_list_version()