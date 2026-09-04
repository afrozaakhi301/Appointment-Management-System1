from .models import ActivityLog


def log_activity(user, action):
    """
    Helper function to record an activity in the database.
    Does not raise exceptions if user is None or logging fails.
    """
    try:
        user_obj = user if (user and user.is_authenticated) else None
        ActivityLog.objects.create(
            user=user_obj,
            action=action
        )
    except Exception:
        # Avoid crashing primary operations if activity logging encounters an issue
        pass
