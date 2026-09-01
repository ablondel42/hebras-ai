"""Unit tests for google_sdk and google_adk integrations."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.antigravity import Agent, LocalOpenAIAgentConfig
from google.antigravity.hooks import policy

from integrations import (
    BaseHebrasAdapter,
    BaseIntegrationConfig,
    HebrasADKAgent,
    HebrasADKConfig,
    HebrasAntigravityAgent,
    HebrasLLM,
    create_adk_config,
    create_antigravity_agent,
    get_antigravity_config,
    stream_agent_response,
)


class TestGoogleSDKIntegration:
    """Tests for google_sdk_integration helpers and HebrasAntigravityAgent."""

    def test_get_antigravity_config_defaults(self):
        config = get_antigravity_config()
        assert isinstance(config, LocalOpenAIAgentConfig)
        assert config.base_url == "http://localhost:8000/v1"
        assert config.model == "Gemini 3.7 Flash"
        assert len(config.policies) == 1

    def test_get_antigravity_config_custom(self):
        def sample_tool(x: int) -> int:
            return x + 1

        config = get_antigravity_config(
            base_url="http://127.0.0.1:9000/v1",
            model="Claude Sonnet 4.6",
            system_instructions="Custom prompt",
            tools=[sample_tool],
            policies=[policy.allow_all()],
        )
        assert config.base_url == "http://127.0.0.1:9000/v1"
        assert config.model == "Claude Sonnet 4.6"
        assert config.system_instructions == "Custom prompt"
        assert len(config.tools) == 1

    def test_hebras_antigravity_agent_init(self):
        agent_wrapper = HebrasAntigravityAgent(
            base_url="http://localhost:8000/v1",
            model="Gemini 3.7 Flash",
            system_instructions="Test agent",
        )
        assert isinstance(agent_wrapper.agent, Agent)
        assert isinstance(agent_wrapper.config, LocalOpenAIAgentConfig)
        assert agent_wrapper.config.base_url == "http://localhost:8000/v1"

    def test_hebras_antigravity_agent_with_base_config(self):
        base_cfg = BaseIntegrationConfig(
            api_base="http://custom:8000/v1",
            model="Gemini 3.1 Pro",
            agent="code_reviewer",
        )
        agent_wrapper = HebrasAntigravityAgent(config=base_cfg)
        assert agent_wrapper.config.base_url == "http://custom:8000/v1"
        assert agent_wrapper.config.model == "Gemini 3.1 Pro"

    @pytest.mark.asyncio
    async def test_hebras_antigravity_agent_stream(self):
        agent_wrapper = HebrasAntigravityAgent(base_url="http://localhost:8000/v1")

        async def mock_tokens():
            for tok in ["Hebras", " ", "stream"]:
                yield tok

        agent_wrapper._agent.chat = AsyncMock(return_value=mock_tokens())

        tokens = []
        async for tok in agent_wrapper.stream("Hello"):
            tokens.append(tok)

        assert "".join(tokens) == "Hebras stream"

    @pytest.mark.asyncio
    async def test_stream_agent_response_with_wrapper(self):
        agent_wrapper = HebrasAntigravityAgent(base_url="http://localhost:8000/v1")

        async def mock_tokens():
            for tok in ["Token", "1"]:
                yield tok

        agent_wrapper._agent.chat = AsyncMock(return_value=mock_tokens())

        tokens = []
        async for tok in stream_agent_response(agent_wrapper, "Hello"):
            tokens.append(tok)

        assert "".join(tokens) == "Token1"

    def test_create_antigravity_agent_helper(self):
        agent = create_antigravity_agent(
            base_url="http://localhost:8000/v1",
            model="Gemini 3.7 Flash",
        )
        assert isinstance(agent, Agent)
        assert agent._config.base_url == "http://localhost:8000/v1"

    def test_top_level_package_exports(self):
        assert create_antigravity_agent is not None
        assert get_antigravity_config is not None
        assert HebrasAntigravityAgent is not None
        assert HebrasLLM is not None
        assert HebrasADKConfig is not None
        assert HebrasADKAgent is not None
        assert BaseIntegrationConfig is not None
        assert BaseHebrasAdapter is not None


class TestGoogleADKIntegration:
    """Tests for google_adk integration classes."""

    def test_create_adk_config(self):
        cfg = create_adk_config(
            base_url="http://localhost:8000/v1",
            model="Gemini 3.7 Flash",
            system_instruction="ADK prompt",
        )
        assert isinstance(cfg, HebrasADKConfig)
        assert cfg.api_base == "http://localhost:8000/v1"
        assert cfg.model == "Gemini 3.7 Flash"
        assert cfg.system_instruction == "ADK prompt"
        assert cfg.tools == []

    def test_hebras_adk_agent_complete(self):
        agent = HebrasADKAgent(
            base_url="http://testserver/v1",
            model="Gemini 3.7 Flash",
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ADK response"}}],
            "system_fingerprint": "adk-session-123",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as MockClient:
            mock_client_inst = MagicMock()
            mock_client_inst.post.return_value = mock_resp
            MockClient.return_value.__enter__.return_value = mock_client_inst

            res = agent.complete("Hello ADK")
            assert res == "ADK response"
            assert agent.conversation_id == "adk-session-123"

    @pytest.mark.asyncio
    async def test_hebras_adk_agent_acomplete(self):
        agent = HebrasADKAgent(
            base_url="http://testserver/v1",
            model="Gemini 3.7 Flash",
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ADK async response"}}],
            "system_fingerprint": "adk-async-123",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_inst = MagicMock()
            mock_inst.post = AsyncMock(return_value=mock_resp)
            MockAsyncClient.return_value.__aenter__.return_value = mock_inst

            res = await agent.acomplete("Hello Async ADK")
            assert res == "ADK async response"
            assert agent.conversation_id == "adk-async-123"
