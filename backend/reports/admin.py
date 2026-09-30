from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "category",
        "status",
        "uploaded_at",
    )

    search_fields = (
        "raw_text",
        "user__username",
    )

    list_filter = (
        "category",
        "status",
    )

    ordering = (
        "-uploaded_at",
    )

    readonly_fields = (
        "user",
        "uploaded_at",
    )