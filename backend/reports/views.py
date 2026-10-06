
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator

from .extraction import extract_text_from_report, ExtractionError
from .forms import ReportForm
from .models import Report, Translation
from .tasks import process_report


def _run_extraction(request, report):
    """
    Attempt to populate report.extracted_text from its attached file.

    Skipped when there's no file, or when extracted_text is already
    populated. Never touches report.raw_text.
    """

    if not report.file or report.extracted_text.strip():
        return

    try:
        report.extracted_text = extract_text_from_report(report)
        report.save(update_fields=["extracted_text"])

    except ExtractionError as exc:
        report.status = "failed"
        report.save(update_fields=["status"])
        messages.error(request, str(exc))


@login_required
def upload_report(request):

    if request.method == "POST":
        form = ReportForm(request.POST, request.FILES)

        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.save()

            _run_extraction(request, report)

            if report.status != "failed":
                messages.success(request, "Report uploaded successfully.")

            return redirect("report_list")

    else:
        form = ReportForm()

    return render(
        request,
        "reports/upload_report.html",
        {"form": form}
    )


@login_required
def report_list(request):

    search = request.GET.get("search", "")
    category = request.GET.get("category", "")
    status = request.GET.get("status", "")

    reports = Report.objects.filter(
        user=request.user
    ).order_by("-uploaded_at")

    # Search filter
    if search:
        reports = reports.filter(
            raw_text__icontains=search
        )

    # Category filter
    if category:
        reports = reports.filter(
            category=category
        )

    # Status filter
    if status:
        reports = reports.filter(
            status=status
        )

    # Pagination
    paginator = Paginator(reports, 10)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "reports/report_list.html",
        {
            "reports": page_obj,
            "page_obj": page_obj,
            "search": search,
            "category": category,
            "status": status,
        }
    )


@login_required
def report_detail(request, report_id):

    report = get_object_or_404(
        Report,
        id=report_id,
        user=request.user
    )

    return render(
        request,
        "reports/report_detail.html",
        {"report": report}
    )


@login_required
def report_update(request, report_id):

    report = get_object_or_404(
        Report,
        id=report_id,
        user=request.user
    )

    if request.method == "POST":

        old_file = report.file

        form = ReportForm(
            request.POST,
            request.FILES,
            instance=report
        )

        if form.is_valid():

            updated_report = form.save()

            old_file_name = old_file.name if old_file else None
            new_file_name = (
                updated_report.file.name if updated_report.file else None
            )
            file_changed = old_file_name != new_file_name

            if old_file and old_file_name and old_file_name != new_file_name:
                old_file.delete(save=False)

            if file_changed:
                updated_report.extracted_text = ""
                updated_report.save(update_fields=["extracted_text"])

            _run_extraction(request, updated_report)

            if updated_report.status != "failed":
                messages.success(request, "Report updated successfully.")

            return redirect(
                "report_detail",
                report_id=report.id
            )

    else:

        form = ReportForm(
            instance=report
        )

    return render(
        request,
        "reports/report_update.html",
        {
            "form": form,
            "report": report
        }
    )


@login_required
def translate_report_view(request, report_id):

    report = get_object_or_404(
        Report,
        id=report_id,
        user=request.user
    )

    if request.method == "POST":

        Translation.objects.update_or_create(
            report=report,
            defaults={"processing_status": "pending", "error_message": ""},
        )

        task = process_report.delay(report.id)

        report.task_id = task.id
        report.save(update_fields=["task_id"])

        messages.success(
            request,
            "Report translation has started."
        )

    return redirect(
        "report_detail",
        report_id=report.id
    )
    
@login_required
def report_status_view(request, report_id):

    report = get_object_or_404(
        Report,
        id=report_id,
        user=request.user
    )

    return JsonResponse({
        "status": report.status,
        "has_translation": hasattr(report, "translation"),
    })


@login_required
def translate_status_view(request, report_id):

    report = get_object_or_404(
        Report,
        id=report_id,
        user=request.user
    )

    if hasattr(report, "translation"):
        return JsonResponse({
            "processing_status": report.translation.processing_status,
            "error_message": report.translation.error_message,
        })

    return JsonResponse({
        "processing_status": "",
        "error_message": "",
    })


@login_required
def report_delete(request, report_id):

    report = get_object_or_404(
        Report,
        id=report_id,
        user=request.user
    )

    if request.method == "POST":

        if report.file:
            report.file.delete(save=False)

        report.delete()

        messages.success(request, "Report deleted.")

        return redirect("report_list")

    return render(
        request,
        "reports/report_delete.html",
        {"report": report}
    )


@login_required
def profile(request):

    user = request.user

    if request.method == "POST":

        user.username = request.POST.get("username", "").strip()
        user.email = request.POST.get("email", "").strip()
        user.first_name = request.POST.get("first_name", "").strip()
        user.last_name = request.POST.get("last_name", "").strip()

        user.save()

        messages.success(request, "Profile updated successfully.")

        return redirect("profile")

    return render(
        request,
        "reports/profile.html",
        {
            "user": user
        }
    )


@login_required
def change_password(request):

    if request.method == "POST":

        form = PasswordChangeForm(
            request.user,
            request.POST
        )

        if form.is_valid():

            user = form.save()

            update_session_auth_hash(
                request,
                user
            )

            messages.success(request, "Password changed successfully.")

            return redirect("profile")

    else:

        form = PasswordChangeForm(
            request.user
        )

    return render(
        request,
        "reports/change_password.html",
        {
            "form": form
        }
    )
