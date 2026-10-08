from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mass_mail
from django.db.models import Q


def notify_new_review(review):
    location = review.location
    users = (
        get_user_model().objects
        .filter(Q(pk=location.author_id) | Q(subscriptions__location=location))
        .exclude(pk=review.author_id)
        .exclude(email="")
        .distinct()
    )
    subject = f"Новий відгук до «{location.title}»"
    body = f"{review.author.username} залишив(ла) відгук ({review.rating}/5):\n\n{review.comment}"
    messages = [(subject, body, settings.DEFAULT_FROM_EMAIL, [u.email]) for u in users]
    if messages:
        send_mass_mail(messages, fail_silently=True)

