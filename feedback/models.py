from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Feedback(models.Model):
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        related_name="feedback"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    comments = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        from appointments.models import Appointment
        if self.appointment_id and self.appointment.status != Appointment.Status.COMPLETED:
            raise ValidationError("Feedback can only be submitted for Completed appointments.")

    def __str__(self):
        return f"Feedback ({self.rating}★) for Appt #{self.appointment_id}"
