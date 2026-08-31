"""GET /v1/models — Dynamic foundational LLM models discovery via Antigravity CLI."""
import asyncio
import logging
import re
import time

from fastapi import APIRouter

from backend.config import settings
from backend.safe_runner import safe_run_command
from backend.types import ModelInfo, ModelListResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory cache for discovered models and catalog mapping
_cache_lock = asyncio.Lock()
_cached_models: list[ModelInfo] | None = None
_cached_catalog: dict[str, dict[str, str]] | None = None
_last_cache_time: float = 0.0


def clean_model_name(name: str) -> str:
    """Strip reflection/thinking qualifiers (e.g. '(High)', '(Medium)', '(Low)', '(Thinking)').

    Args:
        name: Raw model display name.

    Returns:
        Clean, base model name.
    """
    cleaned = re.sub(r"\s*\((?:High|Medium|Low|Thinking)\)\s*", "", name, flags=re.IGNORECASE)
    return cleaned.strip()


def extract_effort(name: str) -> str | None:
    """Extract effort or thinking qualifier from model name."""
    match = re.search(r"\((High|Medium|Low|Thinking)\)", name, re.IGNORECASE)
    return match.group(1).lower() if match else None


async def discover_models_catalog(
    use_cache: bool = True,
) -> tuple[list[ModelInfo], dict[str, dict[str, str]]]:
    """Execute 'agy models' to dynamically discover models and build a variant catalog.

    Returns:
        Tuple of (clean_model_info_list, variant_catalog_map).
    """
    global _cached_models, _cached_catalog, _last_cache_time

    async with _cache_lock:
        now = time.monotonic()
        if (
            use_cache
            and _cached_models is not None
            and _cached_catalog is not None
            and (now - _last_cache_time) < settings.model_cache_ttl
        ):
            return _cached_models, _cached_catalog

        models_list: list[ModelInfo] = []
        catalog: dict[str, dict[str, str]] = {}
        seen_clean_names: set[str] = set()

        try:
            res = await safe_run_command(
                [settings.agy_binary, "models"],
                timeout=10,
                override_stdin_devnull=True,
            )
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.splitlines():
                    line_strip = line.strip()
                    if not line_strip:
                        continue
                    parts = line_strip.split("\t", 1)
                    slug = parts[0].strip()
                    raw_name = parts[1].strip() if len(parts) > 1 else slug
                    clean_name = clean_model_name(raw_name)
                    effort = extract_effort(raw_name) or "high"

                    key = clean_name.lower()
                    if key not in catalog:
                        catalog[key] = {}
                        catalog[key]["_clean_name"] = clean_name
                    catalog[key][effort] = raw_name
                    catalog[key][slug] = raw_name
                    catalog[key]["default"] = catalog[key].get("default") or raw_name

                    if clean_name not in seen_clean_names:
                        seen_clean_names.add(clean_name)
                        models_list.append(
                            ModelInfo(
                                id=clean_name,
                                owned_by="google",
                            )
                        )
        except Exception as e:
            logger.warning(f"Failed to discover models via agy CLI: {e}")

        # Fallback if discovery returned no models
        if not models_list:
            default_clean = clean_model_name(settings.agy_default_model)
            models_list = [ModelInfo(id=default_clean, owned_by="google")]
            key = default_clean.lower()
            catalog = {
                key: {
                    "_clean_name": default_clean,
                    "high": f"{default_clean} (High)",
                    "medium": f"{default_clean} (Medium)",
                    "low": f"{default_clean} (Low)",
                    "default": f"{default_clean} (High)",
                }
            }

        _cached_models = models_list
        _cached_catalog = catalog
        _last_cache_time = now
        return _cached_models, _cached_catalog


async def resolve_agy_model_target(base_model: str, effort: str | None = None) -> tuple[str, str]:
    """Resolve a clean model name and reflection level into the target CLI model argument.

    Args:
        base_model: Clean or raw model name.
        effort: Desired reflection level ('low', 'medium', 'high', None).

    Returns:
        Tuple of (clean_model_name, agy_cli_target_model).
    """
    _, catalog = await discover_models_catalog()

    clean_req = clean_model_name(base_model).lower()
    variants = catalog.get(clean_req)

    # Search case-insensitively or by slug
    if not variants:
        for cat_key, cat_variants in catalog.items():
            if cat_key == clean_req or base_model.lower() in cat_variants:
                variants = cat_variants
                break

    if not variants:
        # Unknown or custom model, pass through or construct effort variant
        clean_name = clean_model_name(base_model)
        if effort and effort.lower() in ("high", "medium", "low"):
            return clean_name, f"{clean_name} ({effort.capitalize()})"
        return clean_name, base_model

    clean_name = variants.get("_clean_name", clean_model_name(base_model))

    if effort:
        eff = effort.lower()
        if eff in variants:
            return clean_name, variants[eff]
        if eff in ("high", "medium", "low") and "thinking" in variants:
            return clean_name, variants["thinking"]
        if eff in ("high", "medium", "low"):
            return clean_name, f"{clean_name} ({eff.capitalize()})"

    # Priority default: high -> thinking -> medium -> low -> first available
    for pref in ("high", "thinking", "medium", "low"):
        if pref in variants:
            return clean_name, variants[pref]

    target = variants.get("default", next(v for k, v in variants.items() if not k.startswith("_")))
    return clean_name, target


@router.get("/models")
async def list_models() -> ModelListResponse:
    """List available clean LLM models supported by Antigravity CLI backend."""
    models, _ = await discover_models_catalog()
    return ModelListResponse(data=models)
