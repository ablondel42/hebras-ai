"""Entry point: python -m app.main or uvicorn api.main:app"""
import uvicorn
from core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
