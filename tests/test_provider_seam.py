"""The provider seam — OPS-02.

Marcus reports that outbound traffic to many domains is blocked inside TTB's
network. That does not bind this prototype, which runs outside it, but a
production deployment would need inference inside their trust boundary. The seam
is what makes that a constructor change rather than a rewrite, so it is worth a
test that it genuinely isolates the rest of the system from the SDK.
"""

import inspect
import re
from pathlib import Path

import pytest

from app.batch import LabelUpload, verify_one
from app.models import LabelFields
from app.providers.base import ExtractionError, ExtractionProvider, StubProvider

ROOT = Path(__file__).parent.parent


def test_ops_02_sdk_is_imported_only_behind_the_seam():
    """Nothing outside app/providers/ may import the vendor SDK.

    Configuration may name the vendor (`anthropic_model`) and the composition root
    may import the concrete provider — that is what a composition root is for.
    What must not happen is a rule, a route, or a batch runner reaching for the
    SDK directly, because that is the coupling the seam exists to prevent.
    """
    sdk_import = re.compile(r"^\s*(?:import\s+anthropic|from\s+anthropic[\s.])", re.M)
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("app/**/*.py")
        if "providers" not in path.parts and sdk_import.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"SDK imported outside the provider seam: {offenders}"


def test_ops_02_interface_is_minimal_enough_to_reimplement():
    """A second provider should need one method, not a study of the first."""
    required = [
        name for name, member in inspect.getmembers(ExtractionProvider, inspect.isfunction)
        if getattr(member, "__isabstractmethod__", False)
    ]
    assert required == ["extract"]


@pytest.mark.asyncio
async def test_ops_02_substituting_a_provider_needs_no_other_change():
    upload = LabelUpload(
        filename="label.png",
        content=(ROOT / "tests" / "fixtures" / "labels" / "compliant_bourbon.png").read_bytes(),
    )
    stub = StubProvider(LabelFields(brand_name="SUBSTITUTED"))
    result = await verify_one(stub, upload)
    assert result.fields.brand_name == "SUBSTITUTED"
    assert stub.calls == 1


@pytest.mark.asyncio
async def test_ops_02_provider_failures_surface_as_extraction_errors():
    """Callers depend on one error type, not on whatever the vendor raises."""
    upload = LabelUpload(
        filename="label.png",
        content=(ROOT / "tests" / "fixtures" / "labels" / "compliant_bourbon.png").read_bytes(),
    )
    with pytest.raises(ExtractionError):
        await verify_one(StubProvider(error=ExtractionError("upstream down", retryable=True)), upload)
