from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ClientProfile, EngineerProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "phone_number", "is_staff")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Custom Role & Details", {"fields": ("role", "phone_number")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Custom Role & Details", {"fields": ("role", "phone_number")}),
    )


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "address")
    search_fields = ("user__username", "user__email", "organization")


@admin.register(EngineerProfile)
class EngineerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "designation", "years_of_experience")
    search_fields = ("user__username", "user__first_name", "user__last_name", "designation")
