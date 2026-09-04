from .models import Notification


def create_notification(user, message, appointment=None):
    """
    Creates a new notification record for a user.
    """
    try:
        if user and user.is_authenticated:
            return Notification.objects.create(
                user=user,
                message=message,
                appointment=appointment
            )
    except Exception:
        pass
    return None
