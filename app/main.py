"""FlowPass FastAPI application entry point.

Kept deliberately thin: route handlers delegate to the engine,
middleware handles cross-cutting concerns, templates render HTML.
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

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard security headers to every response.

    These headers defend against MIME sniffing, clickjacking, referrer leaks,
    and unsanctioned browser features. CSP is intentionally strict; if Maps
    or other third-party scripts need inclusion later, extend it explicitly.
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
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hook.

    Runs once on startup and once on shutdown. Future slices will load
    venue.json, crowd_flow.json, and reason_templates.json here.
    """
    # startup
    yield
    # shutdown


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    Factory pattern so tests can construct fresh app instances.
    """
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(SecurityHeadersMiddleware)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe used by Cloud Run and CI."""
        return {"status": "ok", "version": settings.app_version}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Render the single-screen FlowPass UI.

        For slice 1 this is a placeholder. Slice 3 will wire in the engine.
        """
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"app_name": settings.app_name},
        )

    return app


app = create_app()
