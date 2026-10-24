from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Location
from .services.cache import bump_list_version


# Soft delete goes through save(), so it is covered by post_save. Review
# changes are handled in apps.reviews.signals.
@receiver([post_save, post_delete], sender=Location)
def invalidate_list_cache(sender, **kwargs):
    bump_list_version()
