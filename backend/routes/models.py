"""GET /v1/models — OpenAI-compatible foundational LLM models listing."""
import logging
from collections.abc import Sequence

from fastapi import APIRouter

from backend.config import settings
from backend.types import ModelInfo, ModelListResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def get_available_models(model_names: Sequence[str] | None = None) -> list[ModelInfo]:
    """Return available LLM foundational models supported by Antigravity CLI backend.

    Args:
        model_names: Optional sequence of model names to wrap into ModelInfo objects.

    Returns:
        List of ModelInfo objects for supported foundational models.
    """
    names = model_names if model_names is not None else settings.agy_available_models
    models = [
        ModelInfo(
            id=name,
            owned_by="google",
        )
        for name in names
    ]
    if not models:
        models = [
            ModelInfo(
                id=settings.agy_default_model,
                owned_by="google",
            )
        ]
    return models


@router.get("/models")
async def list_models() -> ModelListResponse:
    """List available LLM models supported by the backend.

    Returns standard OpenAI-compatible ModelInfo entries for foundational models.
    """
    models = get_available_models()
    return ModelListResponse(data=models)
