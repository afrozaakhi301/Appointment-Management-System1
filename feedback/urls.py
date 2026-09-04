from django.urls import path
from . import views

app_name = "feedback"

urlpatterns = [
    path("submit/<int:appointment_id>/", views.submit_feedback_view, name="submit_feedback"),
    path("my-reviews/", views.my_feedback_list_view, name="my_feedback"),
    path("engineer-reviews/", views.engineer_feedback_list_view, name="engineer_reviews"),
]

