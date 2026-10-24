from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.locations.models import LocationView
from apps.locations.querysets import VIEWS_WINDOW_DAYS


class Command(BaseCommand):
    help = "Delete location views older than the popularity window (plus a margin)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-days",
            type=int,
            default=VIEWS_WINDOW_DAYS + 1,
            help="How many days of views to keep (default: window + 1).",
        )

    def handle(self, *args, **options):
        border = timezone.now() - timedelta(days=options["keep_days"])
        deleted, _ = LocationView.objects.filter(viewed_at__lt=border).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} view(s)"))
