from django.http import HttpRequest

from .automated_notifications import build_user_notifications


def notifications_context(request: HttpRequest) -> dict:
    """
    Inject workflow notifications + filter metadata into every template.
    Falls back to empty payload for anonymous sessions.
    """
    if getattr(request, 'user', None) and request.user.is_authenticated:
        notifications, filters = build_user_notifications(request.user)
    else:
        notifications, filters = [], {'qualifications': [], 'statuses': []}

    return {
        'dashboard_notifications': notifications,
        'dashboard_notification_filters': filters,
    }
