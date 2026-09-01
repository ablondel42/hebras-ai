"""Integration tests for GET /v1/models."""
from unittest.mock import AsyncMock, patch

import backend.routes.models as models_module
from backend.safe_runner import ExecutionResult


class TestModelsEndpoint:
    """Tests for the /v1/models endpoint."""

    async def test_list_models_live_or_fallback(self, client):
        """Test /v1/models returns clean model names without reflection qualifiers."""
        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        model_ids = [m["id"] for m in data["data"]]
        # Model IDs should NOT have (High), (Medium), (Low), or (Thinking)
        for mid in model_ids:
            assert "(High)" not in mid
            assert "(Medium)" not in mid
            assert "(Low)" not in mid
            assert "(Thinking)" not in mid

    async def test_dynamic_discovery_parsing(self, client, monkeypatch):
        """Test dynamic discovery parses agy models output and cleans reflection qualifiers."""
        mock_output = (
            "gemini-3.7-flash-high\tGemini 3.7 Flash (High)\n"
            "gemini-3.7-flash-medium\tGemini 3.7 Flash (Medium)\n"
            "gemini-3.7-flash-low\tGemini 3.7 Flash (Low)\n"
            "gemini-3.6-flash-high\tGemini 3.6 Flash (High)\n"
            "claude-sonnet-4-6\tClaude Sonnet 4.6 (Thinking)\n"
            "gpt-oss-120b-medium\tGPT-OSS 120B (Medium)\n"
        )
        mock_res = ExecutionResult(returncode=0, stdout=mock_output, stderr="", duration_ms=10)

        # Clear cached models
        models_module._cached_models = None
        models_module._cached_catalog = None
        models_module._last_cache_time = 0.0

        with patch("backend.routes.models.safe_run_command", new_callable=AsyncMock, return_value=mock_res):
            resp = await client.get("/v1/models")

        assert resp.status_code == 200
        data = resp.json()
        model_ids = [m["id"] for m in data["data"]]
        assert model_ids == ["Gemini 3.7 Flash", "Gemini 3.6 Flash", "Claude Sonnet 4.6", "GPT-OSS 120B"]

    async def test_model_object_format(self, client):
        """Test each model entry has correct OpenAI format."""
        resp = await client.get("/v1/models")
        data = resp.json()
        for model in data["data"]:
            assert model["object"] == "model"
            assert "id" in model
            assert "owned_by" in model
            assert model["owned_by"] == "google"

    async def test_root_endpoint(self, client):
        """Test root endpoint returns version info."""
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "hebras-ai"
        assert "version" in data
