from django.contrib import admin
from .models import Service, Expertise, EngineerExpertise


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")


@admin.register(Expertise)
class ExpertiseAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(EngineerExpertise)
class EngineerExpertiseAdmin(admin.ModelAdmin):
    list_display = ("engineer", "expertise", "proficiency_level")
    list_filter = ("proficiency_level", "expertise")
    search_fields = ("engineer__username", "engineer__first_name", "engineer__last_name", "expertise__name")
