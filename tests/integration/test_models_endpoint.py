"""Integration tests for GET /v1/models."""
import pytest


class TestModelsEndpoint:
    """Tests for the /v1/models endpoint."""

    async def test_list_models(self, client):
        """Test /v1/models returns discovered agents."""
        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        # All model IDs should be prefixed with hebras-
        assert all(m["id"].startswith("hebras-") for m in data["data"])

    async def test_model_object_format(self, client):
        """Test each model entry has correct OpenAI format."""
        resp = await client.get("/v1/models")
        data = resp.json()
        for model in data["data"]:
            assert model["object"] == "model"
            assert "id" in model
            assert "owned_by" in model
            assert model["owned_by"] == "hebras-ai"

    async def test_root_endpoint(self, client):
        """Test root endpoint returns version info."""
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "hebras-ai"
        assert "version" in data
