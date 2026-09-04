from django.urls import path
from . import views

app_name = "scheduling"

urlpatterns = [
    path("availability/", views.manage_availability_view, name="manage_availability"),
    path("leave/", views.manage_leave_view, name="manage_leave"),
    path("api/check/<int:engineer_id>/", views.api_engineer_schedule_check, name="api_check_schedule"),
]
