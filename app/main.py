"""Ascendancy Academy FastAPI application."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import BASE_DIR, settings
from app.routers import api, attendance, auth, books, calendar, courses, documents, grades, home, print_views, settings as settings_router
from app.routers import tasks, theme, usage
from app.seed import seed
from app.services.documents import ensure_library_layout
from app.services.schema import ensure_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    ensure_schema()
    ensure_library_layout()
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

    web_dist = BASE_DIR / "web" / "dist"

    @app.middleware("http")
    async def spa_desk(request: Request, call_next):
        if request.method != "GET":
            return await call_next(request)
        path = request.url.path
        keep = (
            path.startswith("/api")
            or path.startswith("/print")
            or path.startswith("/static")
            or path.startswith("/documents/inline")
            or path.startswith("/documents/download")
            or path.startswith("/teacher/read-pages")
            or path == "/health"
        )
        if keep or os.environ.get("PYTEST_CURRENT_TEST"):
            return await call_next(request)
        index = web_dist / "index.html"
        if not index.is_file():
            return await call_next(request)
        rel = path.lstrip("/")
        if rel:
            candidate = (web_dist / rel).resolve()
            root = web_dist.resolve()
            if str(candidate).startswith(str(root)) and candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(index, media_type="text/html")

    @app.exception_handler(HTTPException)
    async def auth_redirect(request: Request, exc: HTTPException):
        if request.url.path.startswith("/api") or request.url.path.startswith("/teacher/read-pages"):
            detail = exc.detail if isinstance(exc.detail, str) else "Error"
            return JSONResponse({"error": detail}, status_code=exc.status_code)
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

    app.include_router(api.router)
    app.include_router(auth.router)
    app.include_router(home.router)
    app.include_router(courses.router)
    app.include_router(courses.lookup_router)
    app.include_router(books.router)
    app.include_router(grades.router)
    app.include_router(attendance.router)
    app.include_router(calendar.router)
    app.include_router(tasks.router)
    app.include_router(documents.router)
    app.include_router(print_views.router)
    app.include_router(theme.router)
    app.include_router(settings_router.router)
    app.include_router(usage.router)
    return app


app = create_app()
