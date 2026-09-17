"""FastAPI application.

Serves the compiled React bundle and the verification API from a single service,
so the deliverable is one URL (D1, DEL-04).
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="TTB Label Verification", version="0.1.0")

WEB_DIST = Path(__file__).parent.parent / "web" / "dist"


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": app.version})


if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        """Serve index.html for any non-API path so client routing works."""
        return FileResponse(WEB_DIST / "index.html")
