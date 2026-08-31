"""Integration tests for GET /v1/models."""


class TestModelsEndpoint:
    """Tests for the /v1/models endpoint."""

    async def test_list_models(self, client):
        """Test /v1/models returns discovered agents or default model."""
        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        # Model IDs should NOT contain hebras- prefix
        assert not any(m["id"].startswith("hebras-") for m in data["data"])

    async def test_model_object_format(self, client):
        """Test each model entry has correct OpenAI format."""
        resp = await client.get("/v1/models")
        data = resp.json()
        for model in data["data"]:
            assert model["object"] == "model"
            assert "id" in model
            assert "owned_by" in model
            assert model["owned_by"] == "hebras-ai"

    async def test_custom_agent_discovery(self, client, tmp_path, monkeypatch):
        """Test discovering custom agents from directory without prefixes."""
        agent_dir = tmp_path / "code_reviewer"
        agent_dir.mkdir()
        (agent_dir / "code_reviewer.md").write_text("---\nname: code_reviewer\n---\nPrompt")

        monkeypatch.setattr("backend.routes.models.settings.agy_agents_dir", str(tmp_path))

        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        model_ids = [m["id"] for m in data["data"]]
        assert "code_reviewer" in model_ids
        assert not any(m["id"].startswith("hebras-") for m in data["data"])

    async def test_root_endpoint(self, client):
        """Test root endpoint returns version info."""
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "hebras-ai"
        assert "version" in data
