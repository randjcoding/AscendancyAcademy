"""Ascendancy Academy FastAPI application."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import BASE_DIR, settings
from app.routers import attendance, auth, calendar, courses, documents, grades, home, print_views, settings as settings_router
from app.routers import tasks, theme
from app.seed import seed
from app.services.schema import ensure_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    ensure_schema()
    seed()
    yield


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(
        title=settings.site_name,
        lifespan=lifespan,
        debug=False,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    static_dir = BASE_DIR / "app" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "css").mkdir(parents=True, exist_ok=True)
    (static_dir / "js").mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.exception_handler(HTTPException)
    async def auth_redirect(request: Request, exc: HTTPException):
        if exc.status_code == 401:
            path = request.url.path
            door = "teacher"
            if path.startswith("/student") or path.startswith("/grades"):
                door = "student"
            return RedirectResponse(f"/login/{door}?next={path}", status_code=303)
        if exc.status_code == 403 and exc.detail == "Password change required":
            return RedirectResponse("/settings/password?forced=1", status_code=303)
        if exc.status_code == 403 and exc.detail == "Teacher required":
            return RedirectResponse("/student", status_code=303)
        if exc.status_code == 403 and exc.detail == "Student required":
            return RedirectResponse("/teacher", status_code=303)
        from fastapi.exception_handlers import http_exception_handler

        return await http_exception_handler(request, exc)

    @app.get("/health")
    def health():
        return {"status": "ok", "app": settings.site_name}

    app.include_router(auth.router)
    app.include_router(home.router)
    app.include_router(courses.router)
    app.include_router(courses.lookup_router)
    app.include_router(grades.router)
    app.include_router(attendance.router)
    app.include_router(calendar.router)
    app.include_router(tasks.router)
    app.include_router(documents.router)
    app.include_router(print_views.router)
    app.include_router(theme.router)
    app.include_router(settings_router.router)
    return app


app = create_app()
