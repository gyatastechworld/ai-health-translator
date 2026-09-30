import json
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .extraction import ExtractionError, extract_text_from_report
from .models import Report, Translation


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

    def test_owner_can_translate_report(self):

        self.client.login(
            username="translateowner",
            password="password123",
        )

        with patch(
            "reports.services.generate_response",
            return_value=self._valid_ai_response(),
        ):
            response = self.client.post(
                f"/reports/{self.report.id}/translate/"
            )

        self.assertRedirects(response, f"/reports/{self.report.id}/")

        translation = Translation.objects.get(report=self.report)

        self.assertEqual(translation.processing_status, "done")
        self.assertEqual(translation.summary, "Test summary.")

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

        empty_report = Report.objects.create(
            user=self.owner,
            category="other",
            status="uploaded",
        )

        self.client.login(
            username="translateowner",
            password="password123",
        )

        response = self.client.post(
            f"/reports/{empty_report.id}/translate/"
        )

        self.assertRedirects(response, f"/reports/{empty_report.id}/")

        self.assertFalse(
            Translation.objects.filter(report=empty_report).exists()
        )

    def test_provider_failure_is_caught_not_a_500(self):

        self.client.login(
            username="translateowner",
            password="password123",
        )

        with patch(
            "reports.services.generate_response",
            side_effect=RuntimeError("upstream boom"),
        ):
            response = self.client.post(
                f"/reports/{self.report.id}/translate/"
            )

        self.assertRedirects(response, f"/reports/{self.report.id}/")

        translation = Translation.objects.get(report=self.report)

        self.assertEqual(translation.processing_status, "failed")