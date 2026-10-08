from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.locations.models import LocationView
from apps.locations.querysets import VIEWS_WINDOW_DAYS


class Command(BaseCommand):
    help = "Видаляє перегляди локацій, старіші за вікно популярності (+ запас)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-days",
            type=int,
            default=VIEWS_WINDOW_DAYS + 1,
            help="Скільки днів зберігати перегляди (за замовчуванням вікно + 1).",
        )

    def handle(self, *args, **options):
        border = timezone.now() - timedelta(days=options["keep_days"])
        deleted, _ = LocationView.objects.filter(viewed_at__lt=border).delete()
        self.stdout.write(self.style.SUCCESS(f"Видалено переглядів: {deleted}"))