from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.reviews.models import Review
from .models import Location
from .services.cache import bump_list_version

@receiver([post_save, post_delete], sender=Location)
@receiver([post_save, post_delete], sender=Review)
def invalidate_list_cache(sender, **kwargs):
    bump_list_version()