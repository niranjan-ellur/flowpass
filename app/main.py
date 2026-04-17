"""FlowPass FastAPI application entry point.

Kept deliberately thin: route handlers live in app.routes, the engine is
pure, services live at the edge. Middleware handles cross-cutting
concerns; lifespan loads the venue graph once at startup.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import get_settings
from app.routes import router as api_router
from app.services.venue_loader import load_venue

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard security headers to every response.

    Defends against MIME sniffing, clickjacking, referrer leaks, and
    unsanctioned browser features. CSP is intentionally strict; when
    Maps arrives in slice 4 we'll extend it deliberately.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com "
            "https://unpkg.com https://maps.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://maps.googleapis.com; "
            "frame-ancestors 'none';"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the venue graph once at startup, stash it on app.state.

    Every request reads from the in-memory object — zero disk I/O on the
    hot path.
    """
    settings = get_settings()
    app.state.venue = load_venue(settings.venue_data_path)
    yield


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(api_router)

    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe used by Cloud Run and CI."""
        return {"status": "ok", "version": settings.app_version}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Render the single-screen FlowPass UI."""
        venue = request.app.state.venue
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "app_name": settings.app_name,
                "venue": venue,
                "phases": [
                    ("pre_match", "Pre-match"),
                    ("in_play", "In play"),
                    ("innings_break", "Innings break"),
                    ("final_overs", "Final overs"),
                    ("trophy_ceremony", "Trophy ceremony"),
                    ("post_match", "Post-match"),
                ],
                "transit_modes": [
                    ("metro", "Metro"),
                    ("car", "Car"),
                    ("rideshare", "Rideshare"),
                    ("walking", "Walking"),
                ],
            },
        )

    return app


app = create_app()
