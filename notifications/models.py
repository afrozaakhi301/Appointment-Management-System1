from django.conf import settings
from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.user.username} [{'Read' if self.is_read else 'Unread'}]: {self.message[:30]}"
