import base64
import mimetypes
import os

import pdfplumber
import pymupdf

from .providers.groq import generate_vision_response


SUPPORTED_PDF_EXTENSIONS = {".pdf"}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

# A scanned PDF's text layer is empty or near-empty. A few stray
# characters (e.g. a page number pdfplumber picked up) shouldn't count
# as "has usable text", so we require a minimum length before trusting it.
MIN_USABLE_TEXT_CHARS = 40

# Rasterizing + sending every page to the vision model costs time and
# API credits, so scanned PDFs only get their first few pages OCR'd.
MAX_SCANNED_PAGES = 3


class ExtractionError(Exception):
    """Raised when a report's attached file cannot be turned into text."""


def _file_extension(file_field):
    return os.path.splitext(file_field.name)[1].lower()


def _extract_pdf_text_layer(file_field):
    """Read embedded text directly from a PDF's text layer, if any."""

    file_field.open("rb")
    try:
        text_chunks = []
        with pdfplumber.open(file_field) as pdf:
            for page in pdf.pages:
                text_chunks.append(page.extract_text() or "")
        return "\n\n".join(text_chunks).strip()
    finally:
        file_field.close()


def _rasterize_pdf_pages(file_field, max_pages=MAX_SCANNED_PAGES):
    """Render a PDF's pages to PNG images, for when there's no text layer."""

    file_field.open("rb")
    try:
        pdf_bytes = file_field.read()
    finally:
        file_field.close()

    images = []
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_number in range(min(len(doc), max_pages)):
            page = doc.load_page(page_number)
            pixmap = page.get_pixmap(dpi=200)
            images.append(pixmap.tobytes("png"))
    finally:
        doc.close()

    return images


def _read_file_bytes(file_field):
    file_field.open("rb")
    try:
        return file_field.read()
    finally:
        file_field.close()


def _transcribe_images(image_byte_list, mime_type="image/png"):
    """Send each image to the vision LLM and stitch the results together."""

    transcripts = []
    for image_bytes in image_byte_list:
        encoded = base64.b64encode(image_bytes).decode("ascii")

        try:
            text = generate_vision_response(encoded, mime_type=mime_type)
        except Exception as exc:
            # Anything the Groq client can raise (auth, rate limit, an
            # unavailable model, a network blip) is an infrastructure
            # problem, not something fixable by retrying the same
            # upload - surface it as a clean, catchable failure instead
            # of letting it crash the request as an unhandled 500.
            raise ExtractionError(
                "Automatic text scanning isn't available for this file "
                "right now. Please add the report text manually by "
                "editing this record."
            ) from exc

        transcripts.append((text or "").strip())

    return "\n\n".join(chunk for chunk in transcripts if chunk).strip()


def extract_text_from_report(report):
    """
    Detect the type of file attached to `report` and return the best
    text we can pull from it:

      PDF   -> try the embedded text layer first (fast, free, exact).
               If that's empty (a scanned PDF), rasterize the first few
               pages and send them to a vision LLM as an OCR fallback.
      image -> send directly to the vision LLM.
      other -> unsupported; raises ExtractionError.

    Raises ExtractionError when the type isn't supported or nothing
    usable could be extracted, so the caller can mark the report as
    failed with a clear message instead of crashing.
    """

    if not report.file:
        raise ExtractionError("No file attached to this report.")

    extension = _file_extension(report.file)

    if extension in SUPPORTED_PDF_EXTENSIONS:
        text = _extract_pdf_text_layer(report.file)

        if len(text) >= MIN_USABLE_TEXT_CHARS:
            return text

        # No usable text layer - this is a scanned PDF, not a text one.
        page_images = _rasterize_pdf_pages(report.file)
        text = _transcribe_images(page_images, mime_type="image/png")

        if not text:
            raise ExtractionError(
                "This PDF appears to be scanned, and no readable text "
                "could be extracted from it."
            )

        return text

    if extension in SUPPORTED_IMAGE_EXTENSIONS:
        image_bytes = _read_file_bytes(report.file)
        guessed_mime, _ = mimetypes.guess_type(report.file.name)
        text = _transcribe_images(
            [image_bytes],
            mime_type=guessed_mime or "image/png",
        )

        if not text:
            raise ExtractionError(
                "No readable text could be found in the uploaded image."
            )

        return text

    raise ExtractionError(
        f"Unsupported file type '{extension or 'unknown'}'. "
        "Please upload a PDF or an image (PNG/JPG)."
    )
