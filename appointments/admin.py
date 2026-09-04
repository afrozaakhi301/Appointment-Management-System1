from django.contrib import admin
from .models import Appointment, AppointmentDocument


class AppointmentDocumentInline(admin.TabularInline):
    model = AppointmentDocument
    extra = 0


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project_title",
        "client",
        "engineer",
        "service",
        "appointment_date",
        "start_time",
        "end_time",
        "status",
        "created_at",
    )
    list_filter = ("status", "appointment_date", "service")
    search_fields = (
        "project_title",
        "client__username",
        "client__first_name",
        "client__last_name",
        "engineer__username",
        "engineer__first_name",
        "engineer__last_name",
    )
    inlines = [AppointmentDocumentInline]


@admin.register(AppointmentDocument)
class AppointmentDocumentAdmin(admin.ModelAdmin):
    list_display = ("appointment", "file", "uploaded_at")
