"""FastAPI application.

Serves the compiled React bundle and the verification API from a single service,
so the deliverable is one URL (D1, DEL-04).
"""

import logging
import os
import subprocess
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import settings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import ExtractionError, ExtractionProvider, StubProvider

log = logging.getLogger("ttb")
WEB_DIST = Path(__file__).parent.parent / "web" / "dist"


@lru_cache(maxsize=1)
def build_revision() -> str:
    """Identify the running build.

    Reported on /api/health so a deploy can be confirmed rather than assumed.
    Comparing the frontend bundle hash is not enough — it does not change when
    only Python does, so that check once passed against a stale server.
    """
    for key in ("RAILWAY_GIT_COMMIT_SHA", "GIT_COMMIT", "SOURCE_COMMIT"):
        value = os.environ.get(key)
        if value:
            return value[:7]
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 — identity is a convenience, not a dependency
        return "unknown"


def build_provider() -> ExtractionProvider:
    """Construct the extraction provider, or a stub if none is configured.

    A missing key must not prevent the service from starting: the health check and
    the interface should come up and say what is wrong, rather than the container
    crash-looping with the reason buried in a platform log.
    """
    try:
        return AnthropicProvider()
    except ExtractionError as exc:
        log.warning("Extraction unavailable: %s", exc.message)
        return StubProvider(error=ExtractionError(exc.message))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """One provider for the process, so HTTP connections are reused across a batch."""
    app.state.provider = build_provider()
    yield
    await app.state.provider.aclose()


app = FastAPI(title="TTB Label Verification", version="0.3.0", lifespan=lifespan)
app.include_router(router)


@app.get("/api/health")
async def health() -> JSONResponse:
    configured = bool(settings.anthropic_api_key)
    return JSONResponse(
        {
            "status": "ok",
            "version": app.version,
            "revision": build_revision(),
            "extraction_configured": configured,
            "model": settings.anthropic_model if configured else None,
        }
    )


# Mounted last: the catch-all must not shadow the API routes above.
if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        """Serve index.html for any non-API path so client routing works."""
        return FileResponse(WEB_DIST / "index.html")
