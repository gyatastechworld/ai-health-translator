from django import forms
from .models import Report


class ReportForm(forms.ModelForm):

    class Meta:
        model = Report
        fields = [
            "raw_text",
            "file",
            "category",
            "status",
        ]
        widgets = {
            "raw_text": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 6,
                "placeholder": "Paste the report text here...",
            }),
            "file": forms.ClearableFileInput(attrs={
                "class": "sr-only",
            }),
            "category": forms.Select(attrs={
                "class": "form-select",
            }),
            "status": forms.Select(attrs={
                "class": "form-select",
            }),
        }