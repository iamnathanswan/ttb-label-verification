"""No secret may reach the client or the repository — OPS-04.

The security review confirmed this by hand once. A test makes it hold: a key
pasted into a component during debugging, or an error path that starts echoing
the credential it was given, would otherwise ship quietly.
"""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")


def test_ops_04_no_key_in_the_built_client_bundle():
    dist = ROOT / "web" / "dist"
    if not dist.is_dir():
        return  # nothing built in this environment; CI builds before testing
    for path in dist.rglob("*"):
        if path.is_file() and path.suffix in {".js", ".css", ".html", ".map"}:
            assert not KEY_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")), path


def test_ops_04_no_key_in_tracked_source():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    for name in tracked:
        path = ROOT / name
        if not path.is_file() or path.suffix in {".png", ".pdf", ".ico", ".woff2"}:
            continue
        assert not KEY_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")), name


def test_ops_04_env_file_is_not_tracked():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    assert ".env" not in tracked


def test_ops_04_no_key_in_git_history():
    """A key removed in a later commit is still a leaked key."""
    history = subprocess.run(
        ["git", "log", "-p", "--all"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout
    assert not KEY_PATTERN.search(history)


@pytest.mark.asyncio
async def test_ops_04_errors_never_echo_the_credential():
    """Drive the real error paths with a known key and assert it never surfaces.

    Checking the source for the word "key" would pass while an f-string three
    lines away interpolated the credential into a message bound for the browser.
    """
    import anthropic
    import httpx

    from app.providers.anthropic_provider import AnthropicProvider
    from app.providers.base import ExtractionError

    sentinel = "sk-ant-" + "S3CRETVALUE0000000000000"
    provider = AnthropicProvider(api_key=sentinel)

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    failures = [
        anthropic.AuthenticationError(
            "invalid x-api-key", response=httpx.Response(401, request=request), body=None
        ),
        anthropic.BadRequestError(
            "credit balance is too low", response=httpx.Response(400, request=request), body=None
        ),
        anthropic.APIConnectionError(request=request),
    ]

    for failure in failures:
        # Bind the exception per iteration; a closure over the loop variable
        # would raise the last failure on every pass.
        def boom(*_args, _failure=failure, **_kwargs):
            raise _failure

        provider._client.messages.create = boom
        with pytest.raises(ExtractionError) as caught:
            await provider.extract(b"\xff\xd8\xff", "image/jpeg")
        assert sentinel not in str(caught.value), f"credential leaked via {type(failure).__name__}"
        assert sentinel not in caught.value.message
