from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("client/", views.client_dashboard, name="client_dashboard"),
    path("engineer/", views.engineer_dashboard, name="engineer_dashboard"),
    path("admin/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/clients/", views.admin_manage_clients, name="manage_clients"),
    path("admin/engineers/", views.admin_manage_engineers, name="manage_engineers"),
    path("admin/engineers/add/", views.admin_add_engineer, name="add_engineer"),
    path("admin/admins/add/", views.admin_add_admin, name="add_admin"),
    path("admin/services/", views.admin_manage_services, name="manage_services"),
    path("admin/appointments/", views.admin_manage_appointments, name="manage_appointments"),
    path("admin/reports/", views.admin_reports, name="admin_reports"),
    path("admin/tracking/", views.admin_appointment_tracking, name="appointment_tracking"),
    path("admin/tracking/export/csv/", views.export_tracking_csv, name="export_tracking_csv"),
    path("admin/activity-logs/", views.admin_activity_logs, name="admin_activity_logs"),
]
