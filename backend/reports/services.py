import json

from .models import Translation
from .prompts import build_translation_prompt
from .providers.groq import generate_response


def parse_ai_response(response_text):
    """
    Convert the raw JSON response from the LLM
    into a Python dictionary.
    """

    try:
        return json.loads(response_text)

    except json.JSONDecodeError as exc:
        raise ValueError(
            "AI response was not valid JSON."
        ) from exc


def validate_ai_response(data):
    """
    Validate the structure of the parsed AI response.
    """

    required_fields = {
        "summary",
        "key_findings",
        "medical_terms",
        "reported_values",
        "questions_for_doctor",
        "limitations",
    }

    if not isinstance(data, dict):
        raise ValueError("AI response must be a JSON object.")

    missing_fields = required_fields - data.keys()

    if missing_fields:
        raise ValueError(
            f"AI response is missing required fields: "
            f"{', '.join(sorted(missing_fields))}"
        )

    if not isinstance(data["summary"], str):
        raise ValueError("summary must be a string.")

    list_fields = [
        "key_findings",
        "medical_terms",
        "reported_values",
        "questions_for_doctor",
        "limitations",
    ]

    for field in list_fields:
        if not isinstance(data[field], list):
            raise ValueError(f"{field} must be a list.")

    for item in data["medical_terms"]:
        if not isinstance(item, dict):
            raise ValueError("Each medical_terms item must be an object.")

        required_term_fields = {
            "term",
            "explanation",
        }

        missing_term_fields = required_term_fields - item.keys()

        if missing_term_fields:
            raise ValueError(
                "Medical term is missing required fields: "
                f"{', '.join(sorted(missing_term_fields))}"
            )

        if not isinstance(item["term"], str):
            raise ValueError("medical_terms.term must be a string.")

        if not isinstance(item["explanation"], str):
            raise ValueError(
                "medical_terms.explanation must be a string."
            )

    for item in data["reported_values"]:
        if not isinstance(item, dict):
            raise ValueError(
                "Each reported_values item must be an object."
            )

        required_value_fields = {
            "name",
            "value",
            "unit",
            "reference_range",
            "report_context",
        }

        missing_value_fields = required_value_fields - item.keys()

        if missing_value_fields:
            raise ValueError(
                "Reported value is missing required fields: "
                f"{', '.join(sorted(missing_value_fields))}"
            )

        for field in required_value_fields:
            if not isinstance(item[field], str):
                raise ValueError(
                    f"reported_values.{field} must be a string."
                )

    return data


def translate_report(report):
    """
    Run the complete AI translation pipeline for a report.
    """

    if report.file and report.extracted_text.strip():
        source_text = report.extracted_text.strip()
    elif report.raw_text.strip():
        source_text = report.raw_text.strip()
    else:
        source_text = ""

    if not source_text:
        raise ValueError("Report does not contain text to process.")

    translation, created = Translation.objects.get_or_create(
        report=report
    )

    translation.processing_status = "processing"
    translation.error_message = ""
    translation.save(
        update_fields=["processing_status", "error_message"]
    )

    try:
        messages = build_translation_prompt(
            report_text=source_text,
            report_category=report.category,
        )

        raw_response = generate_response(messages)

        parsed_response = parse_ai_response(raw_response)

        validated_response = validate_ai_response(parsed_response)

        translation.summary = validated_response["summary"]
        translation.key_findings = validated_response["key_findings"]
        translation.medical_terms = validated_response["medical_terms"]
        translation.reported_values = validated_response["reported_values"]
        translation.questions_for_doctor = (
            validated_response["questions_for_doctor"]
        )
        translation.limitations = validated_response["limitations"]

        translation.processing_status = "done"
        translation.error_message = ""

        translation.save(
            update_fields=[
                "summary",
                "key_findings",
                "medical_terms",
                "reported_values",
                "questions_for_doctor",
                "limitations",
                "processing_status",
                "error_message",
            ]
        )

        return translation

    except Exception as exc:
        translation.processing_status = "failed"
        translation.error_message = str(exc)
        translation.save(
            update_fields=[
                "processing_status",
                "error_message",
            ]
        )

        raise