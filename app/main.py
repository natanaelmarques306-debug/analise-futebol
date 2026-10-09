import asyncio
import secrets
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.provider import FootballAPI
from app.service import AnalysisService
from app.storage import Store

STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None, service: AnalysisService | None = None, start_scheduler: bool = True) -> FastAPI:
    settings = settings or get_settings()
    owns_service = service is None
    if service is None:
        store = Store(settings.database_path)
        service = AnalysisService(settings, store, FootballAPI(settings, store))

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(service.run()) if start_scheduler else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            if owns_service:
                await service.provider.close()
                service.store.close()

    app = FastAPI(title="Análise Futebol", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.service = service
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/docs", include_in_schema=False)
    async def docs():
        return FileResponse(STATIC / "api.html")

    @app.get("/health")
    async def health():
        return {"status": "ok", "configured": bool(settings.api_football_key)}

    @app.get("/api/dashboard")
    async def dashboard():
        return service.dashboard()

    @app.post("/api/refresh")
    async def refresh(authorization: str | None = Header(default=None)):
        if not settings.admin_token:
            raise HTTPException(403, "Atualização manual desativada; o agendador atualiza automaticamente.")
        if not authorization or not secrets.compare_digest(authorization, f"Bearer {settings.admin_token}"):
            raise HTTPException(401, "Token administrativo inválido.")
        return await service.refresh()

    return app


app = create_app()
