from django.urls import path
from . import views

app_name = "services"

urlpatterns = [
    path("", views.service_list_view, name="service_list"),
    path("engineers/", views.engineer_list_view, name="engineer_list"),
    path("engineers/<int:engineer_id>/", views.engineer_detail_view, name="engineer_detail"),
    path("engineers/my-expertise/", views.engineer_manage_expertise, name="manage_my_expertise"),
    path("about-contact/", views.about_contact_view, name="about_contact"),
]
