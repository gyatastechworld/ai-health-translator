from django.urls import path

from . import views


urlpatterns = [
    path(
        "upload/",
        views.upload_report,
        name="upload_report"
    ),

    path(
        "reports/",
        views.report_list,
        name="report_list"
    ),

    path(
        "reports/<int:report_id>/",
        views.report_detail,
        name="report_detail"
    ),

    path(
        "reports/<int:report_id>/edit/",
        views.report_update,
        name="report_update"
    ),

    path(
        "reports/<int:report_id>/delete/",
        views.report_delete,
        name="report_delete"
    ),

    path(
        "reports/<int:report_id>/translate/",
        views.translate_report_view,
        name="translate_report"
    ),

    path(
        "reports/<int:report_id>/translate/status/",
        views.translate_status_view,
        name="translate_status"
    ),

    path(
        "profile/",
        views.profile,
        name="profile"
    ),

    path(
        "profile/password/",
        views.change_password,
        name="change_password"
    ),
    path(
    "reports/<int:report_id>/status/",
    views.report_status_view,
    name="report_status",
    ),
   
]