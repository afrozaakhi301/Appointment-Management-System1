from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class EngineerAvailability(models.Model):
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availabilities",
        limit_choices_to={"role": "Engineer"}
    )
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        verbose_name = "Engineer Availability"
        verbose_name_plural = "Engineer Availabilities"
        ordering = ["day_of_week", "start_time"]

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": "End time must be after start time."})

    def __str__(self):
        day_name = self.get_day_of_week_display()
        return f"{self.engineer.get_full_name() or self.engineer.username} - {day_name} ({self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')})"


class EngineerLeave(models.Model):
    engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leaves",
        limit_choices_to={"role": "Engineer"}
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "End date must be on or after start date."})

    def __str__(self):
        return f"{self.engineer.get_full_name() or self.engineer.username} Leave ({self.start_date} to {self.end_date})"
