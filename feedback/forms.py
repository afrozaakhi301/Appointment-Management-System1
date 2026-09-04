from django import forms
from .models import Feedback


class FeedbackForm(forms.ModelForm):
    RATING_CHOICES = [
        (5, "★★★★★ (5 - Excellent)"),
        (4, "★★★★☆ (4 - Very Good)"),
        (3, "★★★☆☆ (3 - Good)"),
        (2, "★★☆☆☆ (2 - Fair)"),
        (1, "★☆☆☆☆ (1 - Poor)"),
    ]

    rating = forms.TypedChoiceField(
        choices=RATING_CHOICES,
        coerce=int,
        widget=forms.Select(attrs={"class": "form-select", "id": "rating-select"}),
        help_text="Select your overall consultation rating"
    )

    class Meta:
        model = Feedback
        fields = ("rating", "comments")
        widgets = {
            "comments": forms.Textarea(
                attrs={
                    "rows": 5,
                    "class": "form-control",
                    "placeholder": "Write your feedback on the consultation: technical guidance received, problem solving, communication, and recommendations..."
                }
            ),
        }
        labels = {
            "rating": "Overall Consultation Rating (1-5 Stars)",
            "comments": "Consultation Feedback & Comments",
        }

