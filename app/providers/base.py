"""The model boundary (OPS-02).

Every call to an inference API happens behind this interface. Swapping provider —
to Azure-hosted inference for production (OPS-03), or to a stub in tests — is a
constructor change and nothing else.
"""

from abc import ABC, abstractmethod

from app.models import ApplicationFields, LabelFields


class ExtractionError(Exception):
    """Extraction failed in a way the user should be told about.

    Carries a message written for a compliance agent, not a stack trace (UX-07).
    """

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class ExtractionProvider(ABC):
    """Reads printed information off a label image. Makes no compliance judgement."""

    @abstractmethod
    async def extract(self, image_bytes: bytes, media_type: str) -> tuple[LabelFields, dict[str, int]]:
        """Return the fields read from the label, plus token usage.

        Raises:
            ExtractionError: the image could not be processed.
        """

    async def extract_application(self, image_bytes: bytes, media_type: str) -> ApplicationFields:
        """Read a COLA application that could not be read from its form fields.

        Only reached when a form was printed and scanned, so its AcroForm widgets
        are gone. A digitally completed form is read exactly and never arrives here.
        """
        raise ExtractionError("This provider cannot read scanned applications.")

    async def aclose(self) -> None:  # noqa: B027 — intentional no-op default
        """Release any underlying client resources.

        Not abstract: most providers hold none, and forcing every implementation
        to declare an empty method adds noise without safety.
        """
        return None


class StubProvider(ExtractionProvider):
    """Deterministic provider for tests. Never touches the network.

    Rule tests must run without an API key so the suite stays fast and the
    regulatory logic is verified in isolation from model behaviour.
    """

    def __init__(
        self,
        fields: LabelFields | None = None,
        error: ExtractionError | None = None,
        application: ApplicationFields | None = None,
    ):
        self._fields = fields or LabelFields()
        self._application = application or ApplicationFields()
        self._error = error
        self.calls = 0

    async def extract(self, image_bytes: bytes, media_type: str) -> tuple[LabelFields, dict[str, int]]:
        self.calls += 1
        if self._error:
            raise self._error
        return self._fields, {"input_tokens": 0, "output_tokens": 0}

    async def extract_application(self, image_bytes: bytes, media_type: str) -> ApplicationFields:
        if self._error:
            raise self._error
        return self._application
