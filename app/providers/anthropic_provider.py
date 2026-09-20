"""Anthropic-backed extraction (EXT-01..09).

Transcription only. The model is never asked whether a label complies — that
judgement belongs to `app.rules` (D2).

Note on the system prompt: it deliberately does **not** contain the §16.21
warning text. Showing the model the canonical wording invites it to report the
canonical wording, which would silently repair exactly the defects VAL-01 exists
to catch. The model transcribes what is printed; the comparison happens in code.
"""

import base64
import json
import time

import anthropic
from pydantic import ValidationError

from app.config import settings
from app.models import ApplicationFields, LabelFields
from app.providers.base import ExtractionError, ExtractionProvider

MODEL = "claude-sonnet-5"  # see docs/perf.md; override with ANTHROPIC_MODEL
MAX_TOKENS = 2000

SYSTEM_PROMPT = """\
You transcribe information printed on alcohol beverage labels for a US Treasury \
(TTB) compliance workflow. You are a careful reader, not a reviewer.

Rules:
- Report only what is actually printed on the label. Never infer, correct, \
complete, or standardise anything.
- If text is misspelled, oddly capitalised, abbreviated, or worded unusually, \
reproduce it exactly as printed. Do not fix it. Apparent errors are frequently \
the very thing the reviewer needs to see.
- If a text field is absent, return an empty string. If a numeric field is absent, \
return null. Absence is a meaningful finding; a guess is not.
- Make no judgement about whether the label complies with any requirement.

For the government warning, transcribe the complete text verbatim, preserving \
capitalisation, punctuation, and numbering exactly. Then answer the typographic \
questions by observing the rendering:
- is the heading in capital letters
- is the heading in bold type
- is the text following the heading in bold type (report this independently of \
the heading; they frequently differ)
- is the warning set apart from surrounding text by a box, rule, or whitespace
- does the warning sit on a background that contrasts with its text

Answer each of those, and the field-of-vision question, with "yes", "no", or \
"unclear". Use "unclear" honestly: if the rendering does not settle the question, \
say so rather than guessing. A wrong "no" causes a compliant label to be rejected; \
an "unclear" simply routes it to a human.

Also judge whether brand name, class/type designation, and alcohol content are \
all visible at once without turning the container.

Set image_legible to false only when the image genuinely cannot be read — \
severe blur, darkness, glare, or occlusion — and say why. Perspective, moderate \
glare, and imperfect lighting are normal; read through them.

List the name of any field you read with difficulty in low_confidence_fields, so \
it can be routed to a person rather than trusted silently."""

SCHEMA_PREAMBLE = """

Return a single JSON object conforming exactly to this JSON Schema. Emit only \
the object — no prose, no markdown fences, no commentary.

"""

USER_PROMPT = "Transcribe this alcohol beverage label. Respond with only the JSON object."

APPLICATION_SYSTEM = """\
You transcribe a completed US Treasury (TTB) form 5100.31, the application for \
label approval, for a compliance workflow. You are a careful reader, not a reviewer.

Report only what is written on the form. Never infer, correct or complete a value. \
If a field is blank, return an empty string.

The fields you need:
- serial_number: field 4, the year boxes followed by the serial boxes, e.g. "24-0417"
- permit_number: field 2, the plant registry, basic permit or brewer's number
- source_of_product: field 3, exactly "domestic" or "imported" according to which \
box is marked; empty if neither is
- type_of_product: field 5, exactly "wine", "distilled_spirits" or "malt_beverage" \
according to which box is marked; empty if none is
- brand_name: field 6
- fanciful_name: field 7
- applicant_name: field 8, the name and address of the applicant, as one line
- ttb_id: the TTB ID if the form carries one

Return a single JSON object with those keys and nothing else."""

APPLICATION_USER = "Transcribe this COLA application. Respond with only the JSON object."


def _system_prompt() -> str:
    """Instructions plus the target schema.

    The schema is documentation here, not a decoding constraint. Constrained
    decoding against this shape was measured at >120 s per label against a 5 s
    budget (PRF-01); describing the schema and validating afterwards costs ~2 s.
    The whole string is byte-identical per request, so it caches.
    """
    schema = json.dumps(LabelFields.model_json_schema(), separators=(",", ":"))
    return SYSTEM_PROMPT + SCHEMA_PREAMBLE + schema


def _extract_json(text: str) -> str:
    """Recover the JSON object from a response that may carry stray formatting."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    return text[start : end + 1]


class AnthropicProvider(ExtractionProvider):
    """Reads labels via the Anthropic API.

    Latency configuration is driven by PRF-01. Extraction is perception rather
    than reasoning, so effort is held low; the system prompt is cached because it
    is byte-identical for every label in a batch.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or settings.anthropic_api_key
        if not key:
            raise ExtractionError("No ANTHROPIC_API_KEY configured on the server.")
        headers = (
            {"anthropic-workspace-id": settings.anthropic_workspace_id} if settings.anthropic_workspace_id else None
        )
        self._client = anthropic.AsyncAnthropic(api_key=key, default_headers=headers)
        self._model = model or settings.anthropic_model or MODEL

    async def extract(self, image_bytes: bytes, media_type: str) -> tuple[LabelFields, dict[str, int]]:
        started = time.perf_counter()
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": _system_prompt(), "cache_control": {"type": "ephemeral"}}],
                output_config={"effort": "low"},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64.standard_b64encode(image_bytes).decode(),
                                },
                            },
                            {"type": "text", "text": USER_PROMPT},
                        ],
                    }
                ],
            )
        except anthropic.AuthenticationError as exc:
            raise ExtractionError("The server's API credentials were rejected.") from exc
        except anthropic.RateLimitError as exc:
            raise ExtractionError("The service is busy. Try again in a moment.", retryable=True) from exc
        except anthropic.BadRequestError as exc:
            text = str(exc).lower()
            if "credit balance" in text or "billing" in text:
                raise ExtractionError(
                    "The extraction service is not funded. An administrator needs to add "
                    "API credits before labels can be processed."
                ) from exc
            if "workspace" in text:
                raise ExtractionError(
                    "The server's API key is not scoped to a workspace. Set "
                    "ANTHROPIC_WORKSPACE_ID, or use a workspace-scoped key."
                ) from exc
            raise ExtractionError(f"That label could not be processed: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ExtractionError("Could not reach the extraction service.", retryable=True) from exc
        except anthropic.APIStatusError as exc:
            retryable = exc.status_code >= 500
            raise ExtractionError(
                "The extraction service is unavailable." if retryable else f"Extraction failed: {exc.message}",
                retryable=retryable,
            ) from exc

        text = "".join(b.text for b in response.content if b.type == "text")
        try:
            fields = LabelFields.model_validate_json(_extract_json(text))
        except (ValueError, ValidationError) as exc:
            raise ExtractionError("The label could not be read into the expected structure.", retryable=True) from exc

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
            "extract_ms": int((time.perf_counter() - started) * 1000),
        }
        return fields, usage

    async def extract_application(self, image_bytes: bytes, media_type: str) -> ApplicationFields:
        """Read a scanned application by sight (see `ExtractionProvider`)."""
        schema = json.dumps(ApplicationFields.model_json_schema(), separators=(",", ":"))
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=[{
                    "type": "text",
                    "text": APPLICATION_SYSTEM + SCHEMA_PREAMBLE + schema,
                    "cache_control": {"type": "ephemeral"},
                }],
                output_config={"effort": "low"},
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.standard_b64encode(image_bytes).decode(),
                            },
                        },
                        {"type": "text", "text": APPLICATION_USER},
                    ],
                }],
            )
        except anthropic.APIStatusError as exc:
            raise ExtractionError(
                "The application could not be read.", retryable=exc.status_code >= 500
            ) from exc

        text = "".join(b.text for b in response.content if b.type == "text")
        try:
            return ApplicationFields.model_validate_json(_extract_json(text))
        except (ValueError, ValidationError) as exc:
            raise ExtractionError(
                "The application could not be read into the expected structure.", retryable=True
            ) from exc

    async def aclose(self) -> None:
        await self._client.close()
