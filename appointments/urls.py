from django.urls import path
from . import views

app_name = "appointments"

urlpatterns = [
    path("book/", views.book_appointment_view, name="book_appointment"),
    path("my/", views.client_appointments_view, name="client_appointments"),
    path("requests/", views.engineer_requests_view, name="engineer_requests"),
    path("schedule/", views.engineer_schedule_view, name="engineer_schedule"),
    path("<int:appointment_id>/", views.appointment_detail_view, name="appointment_detail"),
    path("<int:appointment_id>/approve/", views.appointment_approve_view, name="appointment_approve"),
    path("<int:appointment_id>/reject/", views.appointment_reject_view, name="appointment_reject"),
    path("<int:appointment_id>/reschedule/", views.appointment_reschedule_view, name="appointment_reschedule"),
    path("<int:appointment_id>/cancel/", views.appointment_cancel_view, name="appointment_cancel"),
    path("<int:appointment_id>/complete/", views.appointment_complete_view, name="appointment_complete"),
    path("<int:appointment_id>/upload-doc/", views.appointment_upload_doc_view, name="appointment_upload_doc"),
]
