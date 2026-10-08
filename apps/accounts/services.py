from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

User = get_user_model()


def send_password_reset_email(user) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = settings.PASSWORD_RESET_URL_TEMPLATE.format(uid=uid, token=token)
    send_mail(
        subject="Скидання пароля",
        message=(
            f"Вітаємо, {user.get_username()}!\n\n"
            f"Щоб скинути пароль, перейдіть за посиланням:\n{link}\n\n"
            f"Або надішліть POST /api/auth/password-reset/confirm/ з полями:\n"
            f"uid: {uid}\ntoken: {token}\nnew_password: <новий пароль>\n\n"
            "Якщо ви не робили цей запит, просто проігноруйте лист."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def request_password_reset(email: str) -> None:
    for user in User.objects.filter(email__iexact=email, is_active=True):
        if user.has_usable_password():
            send_password_reset_email(user)


def confirm_password_reset(uid: str, token: str, new_password: str):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    if not default_token_generator.check_token(user, token):
        return None
    validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user