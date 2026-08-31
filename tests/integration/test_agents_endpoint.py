"""Integration tests for GET /v1/agents."""


class TestAgentsEndpoint:
    """Tests for the /v1/agents endpoint."""

    async def test_list_agents_default(self, client):
        """Test /v1/agents returns at least the default agent."""
        resp = await client.get("/v1/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        agent_ids = [a["id"] for a in data["data"]]
        assert "default" in agent_ids

    async def test_agent_object_format(self, client):
        """Test each agent entry has correct AgentInfo format."""
        resp = await client.get("/v1/agents")
        data = resp.json()
        for agent in data["data"]:
            assert agent["object"] == "agent"
            assert "id" in agent
            assert "name" in agent

    async def test_custom_agent_discovery(self, client, tmp_path, monkeypatch):
        """Test discovering custom agents from markdown files in .agents/agents/."""
        agent_dir = tmp_path / "code_reviewer"
        agent_dir.mkdir()
        (agent_dir / "code_reviewer.md").write_text(
            "---\n"
            "name: code_reviewer\n"
            "description: Expert code reviewer\n"
            "tools:\n"
            "  - read_file(*)\n"
            "commandExecutionPolicy: off\n"
            "---\n"
            "Review instructions..."
        )

        monkeypatch.setattr("backend.routes.agents.settings.agy_agents_dir", str(tmp_path))

        resp = await client.get("/v1/agents")
        assert resp.status_code == 200
        data = resp.json()
        agent_map = {a["id"]: a for a in data["data"]}
        assert "code_reviewer" in agent_map
        assert agent_map["code_reviewer"]["description"] == "Expert code reviewer"
        assert "read_file(*)" in agent_map["code_reviewer"]["tools"]
        assert agent_map["code_reviewer"]["command_execution_policy"] == "off"
