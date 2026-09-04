from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from .models import User


def role_required(allowed_roles):
    """
    Decorator for views that checks if the logged in user has one of the allowed roles.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if user.role in allowed_roles or (User.Role.ADMIN in allowed_roles and user.is_superuser):
                return view_func(request, *args, **kwargs)
            
            messages.error(request, "You are not authorized to access that page.")
            return redirect("accounts:redirect_after_login")
        return _wrapped_view
    return decorator


def client_required(view_func):
    return role_required([User.Role.CLIENT])(view_func)


def engineer_required(view_func):
    return role_required([User.Role.ENGINEER])(view_func)


def admin_required(view_func):
    return role_required([User.Role.ADMIN])(view_func)
