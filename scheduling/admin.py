from django.contrib import admin
from .models import EngineerAvailability, EngineerLeave


@admin.register(EngineerAvailability)
class EngineerAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("engineer", "day_of_week", "start_time", "end_time")
    list_filter = ("day_of_week", "engineer")
    search_fields = ("engineer__username", "engineer__first_name", "engineer__last_name")


@admin.register(EngineerLeave)
class EngineerLeaveAdmin(admin.ModelAdmin):
    list_display = ("engineer", "start_date", "end_date", "reason")
    list_filter = ("start_date", "end_date", "engineer")
    search_fields = ("engineer__username", "engineer__first_name", "engineer__last_name", "reason")
