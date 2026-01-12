import os
import django
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.core.mail import send_mail  # noqa: E402


def main():
    partial = render_to_string(
        "emails/partials/assessment_status_block.html",
        {
            "assessment": None,
            "status": "test",
            "assessment_link": None,
        },
    )
    context_html = render_to_string(
        "emails/status_notification.html",
        {
            "user": type("User", (), {"first_name": "Test", "username": "Tester"})(),
            "status": "Test Notification",
            "assessment": None,
            "qualification": None,
            "timestamp": timezone.now(),
            "partial_html": partial,
        },
    )
    send_mail(
        subject="Test Notification",
        message="Test notification body",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=["bjmbalaka@gmail.com"],
        html_message=context_html,
        fail_silently=False,
    )
    print("Test notification sent to bjmbalaka@gmail.com")


if __name__ == "__main__":
    main()
