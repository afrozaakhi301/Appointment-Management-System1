from django import forms
from accounts.models import User
from .models import EngineerExpertise, Expertise, Service


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ("name", "description", "is_active")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe the consultation service..."}),
        }


class ExpertiseForm(forms.ModelForm):
    class Meta:
        model = Expertise
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Python / Django, Cloud Architecture, DevOps"}),
        }


class EngineerExpertiseForm(forms.ModelForm):
    class Meta:
        model = EngineerExpertise
        fields = ("expertise", "proficiency_level")


class AdminEngineerExpertiseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["engineer"].queryset = User.objects.filter(role=User.Role.ENGINEER, is_active=True)

    class Meta:
        model = EngineerExpertise
        fields = ("engineer", "expertise", "proficiency_level")
