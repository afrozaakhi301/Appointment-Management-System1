from django import forms
from django.core.exceptions import ValidationError
from accounts.models import User
from services.models import Service
from .models import Appointment, AppointmentDocument
from .services import validate_appointment_booking


class AppointmentBookingForm(forms.ModelForm):
    document = forms.FileField(
        required=False,
        help_text="Optional project specification, diagrams, or wireframes (PDF, DOCX, PNG, ZIP, etc.)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.filter(is_active=True)
        self.fields["engineer"].queryset = User.objects.filter(role=User.Role.ENGINEER, is_active=True)
        self.fields["appointment_date"].widget = forms.DateInput(attrs={"type": "date", "class": "form-control"})
        self.fields["start_time"].widget = forms.TimeInput(attrs={"type": "time", "class": "form-control"})
        self.fields["end_time"].widget = forms.TimeInput(attrs={"type": "time", "class": "form-control"})
        self.fields["service"].widget.attrs.update({"class": "form-select"})
        self.fields["engineer"].widget.attrs.update({"class": "form-select"})
        self.fields["project_title"].widget.attrs.update({"class": "form-control", "placeholder": "e.g., Cloud Architecture Assessment"})
        self.fields["project_description"].widget = forms.Textarea(
            attrs={"rows": 4, "class": "form-control", "placeholder": "Describe your project scope, goals, and technical context..."}
        )
        self.fields["requirements"].widget = forms.Textarea(
            attrs={"rows": 3, "class": "form-control", "placeholder": "Specific questions, tech stack requirements, or deliverables expected..."}
        )

    class Meta:
        model = Appointment
        fields = (
            "service",
            "engineer",
            "appointment_date",
            "start_time",
            "end_time",
            "project_title",
            "project_description",
            "requirements",
        )

    def clean(self):
        cleaned_data = super().clean()
        engineer = cleaned_data.get("engineer")
        appointment_date = cleaned_data.get("appointment_date")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if engineer and appointment_date and start_time and end_time:
            try:
                validate_appointment_booking(
                    engineer=engineer,
                    appointment_date=appointment_date,
                    start_time=start_time,
                    end_time=end_time
                )
            except ValidationError as e:
                if hasattr(e, "message_dict"):
                    for field, errors in e.message_dict.items():
                        for err in errors:
                            self.add_error(field if field in self.fields else None, err)
                elif hasattr(e, "messages"):
                    for err in e.messages:
                        self.add_error(None, err)
                else:
                    self.add_error(None, str(e))

        return cleaned_data


class AppointmentRescheduleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["appointment_date"].widget = forms.DateInput(attrs={"type": "date", "class": "form-control"})
        self.fields["start_time"].widget = forms.TimeInput(attrs={"type": "time", "class": "form-control"})
        self.fields["end_time"].widget = forms.TimeInput(attrs={"type": "time", "class": "form-control"})

    class Meta:
        model = Appointment
        fields = ("appointment_date", "start_time", "end_time")

    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get("appointment_date")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if self.instance and self.instance.engineer and appointment_date and start_time and end_time:
            try:
                validate_appointment_booking(
                    engineer=self.instance.engineer,
                    appointment_date=appointment_date,
                    start_time=start_time,
                    end_time=end_time,
                    exclude_appointment_id=self.instance.id
                )
            except ValidationError as e:
                if hasattr(e, "message_dict"):
                    for field, errors in e.message_dict.items():
                        for err in errors:
                            self.add_error(field if field in self.fields else None, err)
                elif hasattr(e, "messages"):
                    for err in e.messages:
                        self.add_error(None, err)
                else:
                    self.add_error(None, str(e))

        return cleaned_data


class AppointmentDocumentUploadForm(forms.ModelForm):
    class Meta:
        model = AppointmentDocument
        fields = ("file",)
        widgets = {
            "file": forms.FileInput(attrs={"class": "form-control"}),
        }
