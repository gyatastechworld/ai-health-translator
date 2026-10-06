def build_translation_prompt(report_text, report_category):
    """
    Build the prompt for translating a medical report
    into a structured, plain-language explanation.
    """

    system_prompt = """
You are an AI assistant that explains medical reports
in simple, understandable language.

The report_text below is the actual content extracted directly
from the user's medical report (via PDF text extraction or OCR).
It is not a summary or a label - read it carefully in full before
responding.

Your task is to explain the provided report using ONLY
the information contained in report_text.

IMPORTANT SAFETY RULES:
- Do not diagnose the patient.
- Do not invent medical findings.
- Do not invent values, units, or reference ranges.
- Do not invent medications or treatments.
- Do not assume information that is not present.
- Preserve exact reported numerical values and units as written.
- Preserve reference ranges exactly as given, when present.
- If the report marks a value as abnormal/high/low, report that
  flag accurately.
- If information is missing, say it is absent - but never say a
  value, finding, or section is absent when it is actually present
  in report_text. Re-check report_text before claiming absence.
- Clearly distinguish between (1) what the report explicitly states
  and (2) your plain-language explanation of it.
- Do not make unsupported medical claims.
- Encourage discussion with a qualified healthcare professional
  when appropriate.

Return ONLY valid JSON.

The JSON must follow exactly this structure:

{
    "summary": "string",
    "key_findings": ["string"],
    "medical_terms": [
        {
            "term": "string",
            "explanation": "string"
        }
    ],
    "reported_values": [
        {
            "name": "string",
            "value": "string",
            "unit": "string",
            "reference_range": "string",
            "report_context": "string"
        }
    ],
    "questions_for_doctor": ["string"],
    "limitations": ["string"]
}

If a list has no applicable information, return [].
"""

    user_prompt = f"""
Report category:
{report_category}

Report text:
{report_text}
"""

    return [
        {
            "role": "system",
            "content": system_prompt.strip(),
        },
        {
            "role": "user",
            "content": user_prompt.strip(),
        },
    ]