"""
URL configuration for tns_ams project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from services.views import home_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    path("accounts/", include("accounts.urls")),
    path("services/", include("services.urls")),
    path("scheduling/", include("scheduling.urls")),
    path("appointments/", include("appointments.urls")),
    path("feedback/", include("feedback.urls")),
    path("notifications/", include("notifications.urls")),
    path("dashboard/", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)