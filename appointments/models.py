from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from services.models import Service


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        APPROVED = "Approved", "Approved"
        RESCHEDULED = "Rescheduled", "Rescheduled"
        CANCELLED = "Cancelled", "Cancelled"
        REJECTED = "Rejected", "Rejected"
        COMPLETED = "Completed", "Completed"

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_appointments",
        limit_choices_to={"role": "Client"}
    )
    engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="engineer_appointments",
        limit_choices_to={"role": "Engineer"}
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="appointments"
    )
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    project_title = models.CharField(max_length=200)
    project_description = models.TextField()
    requirements = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-appointment_date", "-start_time"]

    def clean(self):
        super().clean()
        from .services import validate_appointment_booking
        validate_appointment_booking(
            engineer=self.engineer,
            appointment_date=self.appointment_date,
            start_time=self.start_time,
            end_time=self.end_time,
            exclude_appointment_id=self.id
        )

    def can_reschedule(self):
        return self.status in [self.Status.PENDING, self.Status.APPROVED, self.Status.RESCHEDULED]

    def can_cancel(self):
        return self.status in [self.Status.PENDING, self.Status.APPROVED, self.Status.RESCHEDULED]

    def can_complete(self):
        return self.status in [self.Status.APPROVED, self.Status.RESCHEDULED]

    def __str__(self):
        return f"[{self.status}] {self.project_title} - {self.client.username} & {self.engineer.username} on {self.appointment_date} ({self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')})"


class AppointmentDocument(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="documents"
    )
    file = models.FileField(upload_to="appointment_docs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def filename(self):
        import os
        return os.path.basename(self.file.name)

    def __str__(self):
        return f"Document for Appt #{self.appointment_id}: {self.filename()}"
