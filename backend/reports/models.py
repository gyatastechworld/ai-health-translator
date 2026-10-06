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
        ("failed", "Failed"),
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

    extracted_text = models.TextField(
        blank=True,
        help_text="Text automatically extracted from the uploaded file"
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
    task_id = models.CharField(
    max_length=255,
    blank=True
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.category}"

class Translation(models.Model):

    PROCESSING_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]

    report = models.OneToOneField(
        Report,
        on_delete=models.CASCADE,
        related_name="translation"
    )

    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS_CHOICES,
        default="pending"
    )

    summary = models.TextField(
        blank=True
    )

    key_findings = models.JSONField(
        default=list,
        blank=True
    )

    medical_terms = models.JSONField(
        default=list,
        blank=True
    )

    reported_values = models.JSONField(
        default=list,
        blank=True
    )

    questions_for_doctor = models.JSONField(
        default=list,
        blank=True
    )

    limitations = models.JSONField(
        default=list,
        blank=True
    )

    error_message = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Translation for Report #{self.report.id}"