from django import forms
from .models import EngineerAvailability, EngineerLeave


class EngineerAvailabilityForm(forms.ModelForm):
    class Meta:
        model = EngineerAvailability
        fields = ("day_of_week", "start_time", "end_time")
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "day_of_week": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_time")
        end = cleaned_data.get("end_time")
        if start and end and start >= end:
            self.add_error("end_time", "End time must be after start time.")
        return cleaned_data


class EngineerLeaveForm(forms.ModelForm):
    class Meta:
        model = EngineerLeave
        fields = ("start_date", "end_date", "reason")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "reason": forms.Textarea(attrs={"rows": 3, "class": "form-control", "placeholder": "Reason for leave (vacation, training, sick leave, etc.)..."}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "End date must be on or after start date.")
        return cleaned_data
