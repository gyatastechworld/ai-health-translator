from celery import shared_task

from .models import Report
from .services import translate_report


@shared_task
def process_report(report_id):
    report = Report.objects.get(id=report_id)
    translation = translate_report(report)
    return translation.id