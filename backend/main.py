"""FastAPI application factory and ASGI entry point for hebras-ai backend."""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.logging_config import setup_logging
from backend.routes.chat import router as chat_router
from backend.routes.models import router as models_router
from backend.session_manager import SessionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle for the FastAPI application."""
    setup_logging()
    session_manager = SessionManager()
    await session_manager.start()
    app.state.session_manager = session_manager
    yield
    await session_manager.stop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app with all routers, middleware, and lifespan.
    """
    app = FastAPI(
        title="hebras-ai",
        description="OpenAI-compatible API server powered by AGY CLI",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8080",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers under /v1
    app.include_router(chat_router, prefix="/v1")
    app.include_router(models_router, prefix="/v1")

    # Root endpoint for health check and version
    @app.get("/")
    async def root():
        return {"message": "hebras-ai", "version": "0.1.0"}

    return app


# Default ASGI app instance for uvicorn (e.g. `uvicorn backend.main:app`)
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
