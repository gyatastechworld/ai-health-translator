from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator

from .forms import ReportForm
from .models import Report


@login_required
def upload_report(request):

    if request.method == "POST":
        form = ReportForm(request.POST, request.FILES)

        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.save()

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

    report = Report.objects.get(
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

    report = Report.objects.get(
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

            if (
                old_file
                and old_file.name
                and old_file.name != updated_report.file.name
            ):
                old_file.delete(save=False)

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
def report_delete(request, report_id):

    report = Report.objects.get(
        id=report_id,
        user=request.user
    )

    if request.method == "POST":

        if report.file:
            report.file.delete(save=False)

        report.delete()

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