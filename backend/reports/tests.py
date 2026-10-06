import json
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .extraction import ExtractionError, extract_text_from_report
from .models import Report, Translation
from .services import translate_report


class ReportOwnershipTest(TestCase):

    def setUp(self):

        User = get_user_model()

        self.user1 = User.objects.create_user(
            username="user1",
            password="password123"
        )

        self.user2 = User.objects.create_user(
            username="user2",
            password="password123"
        )

        self.report = Report.objects.create(
            user=self.user1,
            raw_text="Hemoglobin is 12 g/dL",
            category="blood_test",
            status="uploaded"
        )

    def test_owner_can_access_report(self):

        self.client.login(
            username="user1",
            password="password123"
        )

        response = self.client.get(
            f"/reports/{self.report.id}/"
        )

        self.assertEqual(
            response.status_code,
            200
        )

    def test_other_user_cannot_access_report(self):

        self.client.login(
            username="user2",
            password="password123"
        )

        response = self.client.get(
            f"/reports/{self.report.id}/"
        )

        self.assertEqual(
            response.status_code,
            404
        )

    def test_user_sees_only_own_reports(self):

        second_report = Report.objects.create(
            user=self.user1,
            raw_text="User 1 second report",
            category="prescription",
            status="uploaded"
        )

        other_user_report = Report.objects.create(
            user=self.user2,
            raw_text="User 2 private report",
            category="blood_test",
            status="reviewed"
        )

        self.client.login(
            username="user1",
            password="password123"
        )

        response = self.client.get(
            "/reports/"
        )

        reports = response.context["reports"]

        report_ids = [
            report.id
            for report in reports
        ]

        self.assertIn(
            self.report.id,
            report_ids
        )

        self.assertIn(
            second_report.id,
            report_ids
        )

        self.assertNotIn(
            other_user_report.id,
            report_ids
        )

    def test_other_user_cannot_edit_report(self):

        self.client.login(
            username="user2",
            password="password123"
        )

        response = self.client.get(
            f"/reports/{self.report.id}/edit/"
        )

        self.assertEqual(
            response.status_code,
            404
        )

    def test_other_user_cannot_delete_report(self):

        self.client.login(
            username="user2",
            password="password123"
        )

        response = self.client.get(
            f"/reports/{self.report.id}/delete/"
        )

        self.assertEqual(
            response.status_code,
            404
        )
    
    def test_other_user_cannot_update_report(self):

        self.client.login(
            username="user2",
            password="password123"
        )

        response = self.client.post(
            f"/reports/{self.report.id}/edit/",
            {
                "raw_text": "HACKED REPORT",
                "category": "prescription",
                "status": "reviewed",
            }
        )

        self.assertEqual(
            response.status_code,
            404
        )

        self.report.refresh_from_db()

        self.assertEqual(
            self.report.raw_text,
            "Hemoglobin is 12 g/dL"
        )
    
    def test_other_user_cannot_delete_report(self):

        self.client.login(
            username="user2",
            password="password123"
        )

        response = self.client.post(
            f"/reports/{self.report.id}/delete/"
        )

        self.assertEqual(
            response.status_code,
            404
        )

        self.assertTrue(
            Report.objects.filter(
                id=self.report.id
            ).exists()
        )


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ExtractionTests(TestCase):
    """
    Tests for reports.extraction.extract_text_from_report - the
    file -> text pipeline (PDF text layer, scanned-PDF/image OCR
    fallback, unsupported types).

    MEDIA_ROOT is overridden to a temp directory so uploaded test
    files don't get written into the project's real media/ folder.
    Calls to the Groq vision model are mocked out: we're testing our
    own branching logic here, not Groq's API or network reliability.
    """

    def setUp(self):

        User = get_user_model()

        self.user = User.objects.create_user(
            username="extractionuser",
            password="password123"
        )

    def _make_report(self, file_obj=None):

        return Report.objects.create(
            user=self.user,
            category="other",
            status="uploaded",
            file=file_obj,
        )

    def test_no_file_raises(self):

        report = self._make_report()

        with self.assertRaises(ExtractionError):
            extract_text_from_report(report)

    def test_unsupported_file_type_raises(self):

        report = self._make_report(
            SimpleUploadedFile(
                "notes.docx",
                b"not a real docx",
                content_type="application/octet-stream",
            )
        )

        with self.assertRaises(ExtractionError):
            extract_text_from_report(report)

    def test_pdf_with_text_layer_is_extracted_directly(self):

        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "Hemoglobin 13.5 g/dL, within normal range for adults.",
        )
        pdf_bytes = doc.tobytes()
        doc.close()

        report = self._make_report(
            SimpleUploadedFile(
                "report.pdf",
                pdf_bytes,
                content_type="application/pdf",
            )
        )

        with patch("reports.extraction.generate_vision_response") as mock_vision:
            text = extract_text_from_report(report)

        # A real text layer was found, so the (slower, paid) vision
        # fallback should never have been called.
        mock_vision.assert_not_called()
        self.assertIn("Hemoglobin", text)

    def test_scanned_pdf_falls_back_to_vision_model(self):

        import pymupdf

        doc = pymupdf.open()
        doc.new_page()  # blank page - no text layer at all
        pdf_bytes = doc.tobytes()
        doc.close()

        report = self._make_report(
            SimpleUploadedFile(
                "scan.pdf",
                pdf_bytes,
                content_type="application/pdf",
            )
        )

        with patch(
            "reports.extraction.generate_vision_response",
            return_value="Transcribed text from the scanned page.",
        ) as mock_vision:
            text = extract_text_from_report(report)

        mock_vision.assert_called_once()
        self.assertEqual(text, "Transcribed text from the scanned page.")

    def test_vision_provider_failure_raises_extraction_error(self):
        # Regression test: a real production upload hit this exact case
        # (the configured vision model wasn't available on the Groq
        # account) and it crashed the whole request with an unhandled
        # 500 instead of failing the report cleanly.

        import pymupdf

        doc = pymupdf.open()
        doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()

        report = self._make_report(
            SimpleUploadedFile(
                "scan.pdf",
                pdf_bytes,
                content_type="application/pdf",
            )
        )

        with patch(
            "reports.extraction.generate_vision_response",
            side_effect=RuntimeError("model not found"),
        ):
            with self.assertRaises(ExtractionError):
                extract_text_from_report(report)

    def test_image_file_uses_vision_model(self):

        # A minimal 1x1 PNG - just enough bytes to be a valid file.
        png_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000100000001080600000"
            "01f15c4890000000a49444154789c6360000002000155a2415f000000"
            "0049454e44ae426082"
        )

        report = self._make_report(
            SimpleUploadedFile(
                "photo.png",
                png_bytes,
                content_type="image/png",
            )
        )

        with patch(
            "reports.extraction.generate_vision_response",
            return_value="Prescription: Amoxicillin 500mg",
        ) as mock_vision:
            text = extract_text_from_report(report)

        mock_vision.assert_called_once()
        self.assertEqual(text, "Prescription: Amoxicillin 500mg")


class TranslateReportViewTests(TestCase):
    """
    Tests for the /reports/<id>/translate/ view - the "Translate Report"
    button on the detail page. Groq's text call is mocked: we're testing
    our own view/ownership/error-handling logic, not Groq's uptime.
    """

    def setUp(self):

        User = get_user_model()

        self.owner = User.objects.create_user(
            username="translateowner",
            password="password123",
        )
        self.other = User.objects.create_user(
            username="translateother",
            password="password123",
        )

        self.report = Report.objects.create(
            user=self.owner,
            raw_text="Hemoglobin 10.2 g/dL",
            category="blood_test",
            status="uploaded",
        )

    def _valid_ai_response(self):

        return json.dumps({
            "summary": "Test summary.",
            "key_findings": ["Finding one"],
            "medical_terms": [
                {
                    "term": "Hemoglobin",
                    "explanation": "A protein in red blood cells.",
                }
            ],
            "reported_values": [
                {
                    "name": "Hemoglobin",
                    "value": "10.2",
                    "unit": "g/dL",
                    "reference_range": "13.5-17.5 g/dL",
                    "report_context": "blood test",
                }
            ],
            "questions_for_doctor": ["Is this low?"],
            "limitations": [],
        })

    def test_owner_can_queue_translation(self):

        self.client.login(
            username="translateowner",
            password="password123",
        )

        with patch("reports.views.process_report.delay") as mock_delay:
            mock_delay.return_value.id = "fake-task-id-1"
            response = self.client.post(
                f"/reports/{self.report.id}/translate/"
            )

        self.assertRedirects(response, f"/reports/{self.report.id}/")
        mock_delay.assert_called_once_with(self.report.id)

    def test_other_user_cannot_translate_report(self):

        self.client.login(
            username="translateother",
            password="password123",
        )

        response = self.client.post(
            f"/reports/{self.report.id}/translate/"
        )

        self.assertEqual(response.status_code, 404)

        self.assertFalse(
            Translation.objects.filter(report=self.report).exists()
        )

    def test_translate_with_no_text_does_not_crash(self):
        # The view no longer checks for text before queuing - that
        # validation happens inside translate_report(), inside the
        # worker. The view's own job is just to reset the Translation
        # row to "pending" synchronously and queue the task; it should
        # do that without crashing even when there's nothing to
        # translate yet.

        empty_report = Report.objects.create(
            user=self.owner,
            category="other",
            status="uploaded",
        )

        self.client.login(
            username="translateowner",
            password="password123",
        )

        with patch("reports.views.process_report.delay") as mock_delay:
            mock_delay.return_value.id = "fake-task-id-no-text"
            response = self.client.post(
                f"/reports/{empty_report.id}/translate/"
            )

        self.assertRedirects(response, f"/reports/{empty_report.id}/")

        translation = Translation.objects.get(report=empty_report)
        self.assertEqual(translation.processing_status, "pending")

    def test_duplicate_posts_queue_a_task_each_time(self):

        self.client.login(
            username="translateowner",
            password="password123",
        )

        with patch("reports.views.process_report.delay") as mock_delay:
            mock_delay.return_value.id = "fake-task-id-2"
            self.client.post(f"/reports/{self.report.id}/translate/")
            self.client.post(f"/reports/{self.report.id}/translate/")

        self.assertEqual(mock_delay.call_count, 2)

    def test_first_click_shows_processing_before_worker_creates_translation(self):
        # Regression test: the Celery worker runs translate_report()
        # asynchronously, so the view itself resets the Translation row
        # to "pending" synchronously, in the same request as queuing
        # the task, before the worker ever touches it. The very first
        # page the user sees must show the processing state (and keep
        # polling), not "Translation not started yet." with a
        # re-clickable button.

        self.client.login(
            username="translateowner",
            password="password123",
        )

        with patch("reports.views.process_report.delay") as mock_delay:
            mock_delay.return_value.id = "fake-task-id-3"
            response = self.client.post(
                f"/reports/{self.report.id}/translate/",
                follow=True,
            )

        translation = Translation.objects.get(report=self.report)
        self.assertEqual(translation.processing_status, "pending")

        content = response.content.decode()

        self.assertIn("data-translation-poll", content)
        self.assertIn("Translation pending", content)
        self.assertNotIn("Translation not started yet.", content)

    def test_status_endpoint_reports_no_translation(self):

        self.client.login(
            username="translateowner",
            password="password123",
        )

        response = self.client.get(
            f"/reports/{self.report.id}/translate/status/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"processing_status": "", "error_message": ""},
        )

    def test_status_endpoint_reports_current_translation_state(self):

        Translation.objects.create(
            report=self.report,
            processing_status="processing",
        )

        self.client.login(
            username="translateowner",
            password="password123",
        )

        response = self.client.get(
            f"/reports/{self.report.id}/translate/status/"
        )

        self.assertEqual(
            response.json()["processing_status"],
            "processing",
        )

    def test_status_endpoint_never_queues_a_task(self):

        Translation.objects.create(
            report=self.report,
            processing_status="pending",
        )

        self.client.login(
            username="translateowner",
            password="password123",
        )

        with patch("reports.views.process_report.delay") as mock_delay:
            self.client.get(
                f"/reports/{self.report.id}/translate/status/"
            )

        mock_delay.assert_not_called()

    def test_other_user_cannot_read_translation_status(self):

        Translation.objects.create(
            report=self.report,
            processing_status="done",
            summary="Secret summary",
        )

        self.client.login(
            username="translateother",
            password="password123",
        )

        response = self.client.get(
            f"/reports/{self.report.id}/translate/status/"
        )

        self.assertEqual(response.status_code, 404)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SourceTextPriorityTests(TestCase):

    def setUp(self):

        User = get_user_model()

        self.user = User.objects.create_user(
            username="prioritytestuser",
            password="password123",
        )

    def _valid_ai_response(self):

        return json.dumps({
            "summary": "ok",
            "key_findings": [],
            "medical_terms": [],
            "reported_values": [],
            "questions_for_doctor": [],
            "limitations": [],
        })

    def test_upload_extracts_text_even_when_raw_text_is_present(self):

        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "Haemoglobin 9.8 g/dL Low Reference 13.0-17.0 g/dL",
        )
        pdf_bytes = doc.tobytes()
        doc.close()

        self.client.login(
            username="prioritytestuser",
            password="password123",
        )

        response = self.client.post(
            "/upload/",
            {
                "raw_text": "Blood test report",
                "category": "blood_test",
                "status": "uploaded",
                "file": SimpleUploadedFile(
                    "sample_blood_test_report.pdf",
                    pdf_bytes,
                    content_type="application/pdf",
                ),
            },
        )

        self.assertEqual(response.status_code, 302)

        report = Report.objects.get(user=self.user)

        self.assertEqual(report.raw_text, "Blood test report")
        self.assertIn("Haemoglobin", report.extracted_text)

    def test_translate_prefers_extracted_text_when_file_present(self):

        report = Report.objects.create(
            user=self.user,
            category="blood_test",
            status="uploaded",
            raw_text="Blood test report",
            extracted_text="Haemoglobin 9.8 g/dL Low Reference 13.0-17.0 g/dL",
            file=SimpleUploadedFile(
                "sample_blood_test_report.pdf",
                b"%PDF-1.4 fake",
                content_type="application/pdf",
            ),
        )

        with patch(
            "reports.services.generate_response",
            return_value=self._valid_ai_response(),
        ) as mock_generate:
            translate_report(report)

        sent_messages = mock_generate.call_args[0][0]
        user_message_content = sent_messages[1]["content"]

        self.assertIn("Haemoglobin 9.8 g/dL", user_message_content)
        self.assertNotIn("Blood test report", user_message_content)

    def test_translate_falls_back_to_raw_text_when_no_file(self):

        report = Report.objects.create(
            user=self.user,
            category="blood_test",
            status="uploaded",
            raw_text="Haemoglobin 9.8 g/dL",
        )

        with patch(
            "reports.services.generate_response",
            return_value=self._valid_ai_response(),
        ) as mock_generate:
            translate_report(report)

        sent_messages = mock_generate.call_args[0][0]
        user_message_content = sent_messages[1]["content"]

        self.assertIn("Haemoglobin 9.8 g/dL", user_message_content)

    def test_translate_falls_back_to_raw_text_when_extraction_failed(self):

        report = Report.objects.create(
            user=self.user,
            category="blood_test",
            status="failed",
            raw_text="Manually typed: Haemoglobin 9.8 g/dL",
            extracted_text="",
            file=SimpleUploadedFile(
                "scan.pdf",
                b"%PDF-1.4 fake",
                content_type="application/pdf",
            ),
        )

        with patch(
            "reports.services.generate_response",
            return_value=self._valid_ai_response(),
        ) as mock_generate:
            translate_report(report)

        sent_messages = mock_generate.call_args[0][0]
        user_message_content = sent_messages[1]["content"]

        self.assertIn("Manually typed: Haemoglobin 9.8 g/dL", user_message_content)