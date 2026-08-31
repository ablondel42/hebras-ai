"""Integration tests for GET /v1/models."""


class TestModelsEndpoint:
    """Tests for the /v1/models endpoint."""

    async def test_list_models(self, client):
        """Test /v1/models returns supported foundational LLM models."""
        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        model_ids = [m["id"] for m in data["data"]]
        assert "Gemini 3.6 Flash (High)" in model_ids

    async def test_model_object_format(self, client):
        """Test each model entry has correct OpenAI format."""
        resp = await client.get("/v1/models")
        data = resp.json()
        for model in data["data"]:
            assert model["object"] == "model"
            assert "id" in model
            assert "owned_by" in model
            assert model["owned_by"] == "google"

    async def test_custom_models_config(self, client, monkeypatch):
        """Test listing models reflects custom agy_available_models setting."""
        custom_models = ["Gemini 3.5 Pro", "Custom-LLM-v1"]
        monkeypatch.setattr("backend.routes.models.settings.agy_available_models", custom_models)

        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        ids = [m["id"] for m in data["data"]]
        assert ids == custom_models

    async def test_root_endpoint(self, client):
        """Test root endpoint returns version info."""
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "hebras-ai"
        assert "version" in data
