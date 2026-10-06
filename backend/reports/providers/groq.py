import os

from groq import Groq


def generate_response(messages):
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured.")

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        temperature=0,
        max_tokens=12000,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "medical_report_translation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string"
                        },
                        "key_findings": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "medical_terms": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "term": {
                                        "type": "string"
                                    },
                                    "explanation": {
                                        "type": "string"
                                    }
                                },
                                "required": [
                                    "term",
                                    "explanation"
                                ],
                                "additionalProperties": False
                            }
                        },
                        "reported_values": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string"
                                    },
                                    "value": {
                                        "type": "string"
                                    },
                                    "unit": {
                                        "type": "string"
                                    },
                                    "reference_range": {
                                        "type": "string"
                                    },
                                    "report_context": {
                                        "type": "string"
                                    }
                                },
                                "required": [
                                    "name",
                                    "value",
                                    "unit",
                                    "reference_range",
                                    "report_context"
                                ],
                                "additionalProperties": False
                            }
                        },
                        "questions_for_doctor": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "limitations": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "summary",
                        "key_findings",
                        "medical_terms",
                        "reported_values",
                        "questions_for_doctor",
                        "limitations"
                    ],
                    "additionalProperties": False
                }
            }
        },
    )

    return response.choices[0].message.content

def generate_vision_response(base64_image, mime_type="image/png"):
    """
    Send a single image to a vision-capable Groq model and return
    its transcription of the visible text.

    Used as the OCR fallback for scanned PDFs and photographed
    documents, where there is no embedded text layer to read directly.
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured.")

    client = Groq(api_key=api_key)

    # Groq's model lineup (and which ones support image input) changes
    # over time - override via env var if this default is retired.
    # Check https://console.groq.com/docs/vision for the current list.
    vision_model = os.getenv(
        "GROQ_VISION_MODEL",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    )

    response = client.chat.completions.create(
        model=vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Transcribe all readable text from this "
                            "medical document image exactly as written, "
                            "preserving line breaks where possible. "
                            "Return only the transcribed text - no "
                            "commentary, no summary."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        temperature=0,
    )

    return response.choices[0].message.content