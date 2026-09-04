from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, ClientProfile, EngineerProfile


class ClientRegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=150, 
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., John"})
    )
    last_name = forms.CharField(
        max_length=150, 
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Doe"})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "john.doe@company.com"})
    )
    phone_number = forms.CharField(
        max_length=20, 
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+880 1711-000000"})
    )
    organization = forms.CharField(
        max_length=150, 
        required=False, 
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Acme Corp / Startup"})
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "Office address or city"}), 
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "username" in self.fields:
            self.fields["username"].widget.attrs.update({"class": "form-control", "placeholder": "Choose a username"})
        if "password1" in self.fields:
            self.fields["password1"].widget.attrs.update({"class": "form-control", "placeholder": "Create a strong password"})
        if "password2" in self.fields:
            self.fields["password2"].widget.attrs.update({"class": "form-control", "placeholder": "Confirm your password"})

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "organization",
            "address",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CLIENT
        user.phone_number = self.cleaned_data.get("phone_number", "")
        if commit:
            user.save()
            profile, _ = ClientProfile.objects.get_or_create(user=user)
            profile.organization = self.cleaned_data.get("organization", "")
            profile.address = self.cleaned_data.get("address", "")
            profile.save()
        return user


class UserLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your username",
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your password",
            }
        ),
    )


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number")


class ClientProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = ClientProfile
        fields = ("organization", "address")
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }


class EngineerProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = EngineerProfile
        fields = ("designation", "years_of_experience", "bio", "profile_photo")
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }


class AdminEngineerCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    designation = forms.CharField(max_length=100, initial="Senior Software Engineer")
    years_of_experience = forms.IntegerField(min_value=0, initial=3)
    bio = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    profile_photo = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "designation",
            "years_of_experience",
            "bio",
            "profile_photo",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.ENGINEER
        user.phone_number = self.cleaned_data.get("phone_number", "")
        if commit:
            user.save()
            profile, _ = EngineerProfile.objects.get_or_create(user=user)
            profile.designation = self.cleaned_data.get("designation", "Software Engineer")
            profile.years_of_experience = self.cleaned_data.get("years_of_experience", 0)
            profile.bio = self.cleaned_data.get("bio", "")
            if self.cleaned_data.get("profile_photo"):
                profile.profile_photo = self.cleaned_data.get("profile_photo")
            profile.save()
        return user


class AdminCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.ADMIN
        user.is_staff = True
        user.phone_number = self.cleaned_data.get("phone_number", "")
        if commit:
            user.save()
        return user