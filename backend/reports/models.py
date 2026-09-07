from django.db import models
from django.conf import settings


class Report(models.Model):

    CATEGORY_CHOICES = [
        ("blood_test", "Blood Test"),
        ("prescription", "Prescription"),
        ("discharge_summary", "Discharge Summary"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("reviewed", "Reviewed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports"
    )

    raw_text = models.TextField(
        blank=True,
        help_text="Original report text as pasted/uploaded"
    )

    file = models.FileField(
        upload_to="reports/",
        blank=True,
        null=True
    )

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="other"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="uploaded"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.category}"