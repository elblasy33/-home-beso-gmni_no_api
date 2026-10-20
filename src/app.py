import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.api.router import api_router
from src.engine.mock_site import mock_router
from src.engine.browser_manager import browser_manager
from src.queue.job_worker import job_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure dirs, start queue worker
    settings.ensure_directories()
    job_worker.start()
    yield
    # Shutdown: stop worker and browser cleanly
    await job_worker.stop()
    await browser_manager.close()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Browser AI Automation Agent",
        description="Configuration-driven browser automation platform powered by Playwright and FastAPI",
        version="1.0.0",
        lifespan=lifespan
    )

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount Artifacts & Static Assets
    artifacts_dir = Path(settings.ARTIFACTS_DIR)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/artifacts", StaticFiles(directory=str(artifacts_dir)), name="artifacts")

    static_dir = Path(__file__).resolve().parent.parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include API routes
    app.include_router(api_router)

    # Include local mock site router
    app.include_router(mock_router)

    @app.get("/", response_class=FileResponse)
    async def index():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse("<h1>Browser AI Automation Agent is running</h1>")

    return app

app = create_app()
