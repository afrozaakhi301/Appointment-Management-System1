from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from dashboard.utils import log_activity
from .forms import (
    ClientProfileUpdateForm,
    ClientRegistrationForm,
    EngineerProfileUpdateForm,
    UserLoginForm,
    UserUpdateForm,
)
from .models import ClientProfile, EngineerProfile, User


def register_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:redirect_after_login")

    if request.method == "POST":
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            log_activity(user, f"User registered as Client ({user.username})")
            login(request, user)
            messages.success(request, f"Welcome to TNS AMS, {user.first_name or user.username}! Your client account has been created.")
            return redirect("accounts:redirect_after_login")
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = ClientRegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form}
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:redirect_after_login")

    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user is not None:
                if not user.is_active:
                    messages.error(request, "This account is inactive. Please contact system administration.")
                    return render(request, "accounts/login.html", {"form": form})

                login(request, user)
                log_activity(user, f"User logged in ({user.username} - {user.role})")
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                
                if next_url and not next_url.startswith("//") and not next_url.startswith("http"):
                    return redirect(next_url)
                return redirect("accounts:redirect_after_login")

            form.add_error(None, "Invalid username or password.")
            messages.error(request, "Invalid username or password.")
    else:
        form = UserLoginForm()

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": next_url}
    )


@login_required
def redirect_after_login(request):
    user = request.user
    if user.role == User.Role.CLIENT:
        return redirect("dashboard:client_dashboard")
    elif user.role == User.Role.ENGINEER:
        return redirect("dashboard:engineer_dashboard")
    elif user.role == User.Role.ADMIN or user.is_superuser:
        return redirect("dashboard:admin_dashboard")
    return redirect("accounts:login")


@login_required
def profile_view(request):
    user = request.user
    client_profile = None
    engineer_profile = None

    if user.role == User.Role.CLIENT:
        client_profile, _ = ClientProfile.objects.get_or_create(user=user)
    elif user.role == User.Role.ENGINEER:
        engineer_profile, _ = EngineerProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        u_form = UserUpdateForm(request.POST, instance=user)
        p_form = None

        if user.role == User.Role.CLIENT:
            p_form = ClientProfileUpdateForm(request.POST, instance=client_profile)
        elif user.role == User.Role.ENGINEER:
            p_form = EngineerProfileUpdateForm(request.POST, request.FILES, instance=engineer_profile)

        if u_form.is_valid() and (p_form is None or p_form.is_valid()):
            u_form.save()
            if p_form:
                p_form.save()
            log_activity(user, "Updated profile information")
            messages.success(request, "Your profile has been successfully updated.")
            return redirect("accounts:profile")
        else:
            messages.error(request, "Please correct the errors in the profile form.")
    else:
        u_form = UserUpdateForm(instance=user)
        if user.role == User.Role.CLIENT:
            p_form = ClientProfileUpdateForm(instance=client_profile)
        elif user.role == User.Role.ENGINEER:
            p_form = EngineerProfileUpdateForm(instance=engineer_profile)
        else:
            p_form = None

    return render(
        request,
        "accounts/profile.html",
        {
            "u_form": u_form,
            "p_form": p_form,
            "client_profile": client_profile,
            "engineer_profile": engineer_profile,
        }
    )


def logout_view(request):
    if request.user.is_authenticated:
        log_activity(request.user, f"User logged out ({request.user.username})")
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("accounts:login")
