from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list_view, name="notification_list"),
    path("<int:notification_id>/", views.notification_detail_view, name="notification_detail"),
    path("<int:notification_id>/toggle-read/", views.toggle_notification_read_view, name="toggle_read"),
    path("<int:notification_id>/delete/", views.delete_notification_view, name="delete_notification"),
    path("<int:notification_id>/read/", views.mark_as_read_view, name="mark_as_read"),
    path("mark-read/<int:notification_id>/", views.mark_as_read_view, name="mark_read_alt"),
    path("read-all/", views.mark_all_as_read_view, name="mark_all_as_read"),
    path("mark-all-read/", views.mark_all_as_read_view, name="mark_all_read_alt"),
]
