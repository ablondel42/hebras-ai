"""Unit tests for integrations base classes and configurations."""
from collections.abc import AsyncIterator

from integrations.base import BaseHebrasAdapter, BaseIntegrationConfig


class SampleAdapter(BaseHebrasAdapter):
    """Sample concrete implementation for testing BaseHebrasAdapter."""

    def complete(self, prompt: str, **kwargs) -> str:
        return f"Echo: {prompt}"

    async def acomplete(self, prompt: str, **kwargs) -> str:
        return f"Async Echo: {prompt}"

    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        for token in prompt.split():
            yield token


class TestBaseIntegrationConfig:
    def test_default_config(self):
        cfg = BaseIntegrationConfig()
        assert cfg.api_base == "http://localhost:8000/v1"
        assert cfg.model == "Gemini 3.7 Flash"
        assert cfg.agent == "default"
        assert cfg.reflection == "high"
        assert cfg.interactive is False
        assert cfg.mode is None
        assert cfg.dangerously_skip_permissions is False
        assert cfg.timeout == 180.0
        assert cfg.conversation_id is None

    def test_build_payload_defaults(self):
        cfg = BaseIntegrationConfig()
        payload = cfg.build_payload("Hello world")
        assert payload["model"] == "Gemini 3.7 Flash"
        assert payload["agent"] == "default"
        assert payload["reflection"] == "high"
        assert payload["interactive"] is False
        assert payload["dangerously_skip_permissions"] is False
        assert payload["messages"] == [{"role": "user", "content": "Hello world"}]
        assert "stream" not in payload
        assert "mode" not in payload
        assert "conversation_id" not in payload

    def test_build_payload_custom(self):
        cfg = BaseIntegrationConfig(
            model="Claude Sonnet 4.6",
            agent="code_writer",
            reflection="medium",
            interactive=True,
            mode="plan",
            dangerously_skip_permissions=True,
            conversation_id="conv-1234",
        )
        extra = [{"role": "system", "content": "You are a coding assistant."}]
        payload = cfg.build_payload("Write test", stream=True, extra_messages=extra)

        assert payload["model"] == "Claude Sonnet 4.6"
        assert payload["agent"] == "code_writer"
        assert payload["reflection"] == "medium"
        assert payload["interactive"] is True
        assert payload["mode"] == "plan"
        assert payload["dangerously_skip_permissions"] is True
        assert payload["stream"] is True
        assert payload["conversation_id"] == "conv-1234"
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"


class TestBaseHebrasAdapter:
    def test_adapter_initialization(self):
        cfg = BaseIntegrationConfig(model="GPT-OSS 120B", conversation_id="conv-abc")
        adapter = SampleAdapter(config=cfg)
        assert adapter.conversation_id == "conv-abc"
        assert adapter.config.model == "GPT-OSS 120B"

        adapter.conversation_id = "conv-xyz"
        assert adapter.conversation_id == "conv-xyz"
        assert adapter.config.conversation_id == "conv-xyz"

    def test_adapter_complete(self):
        adapter = SampleAdapter()
        res = adapter.complete("Hello")
        assert res == "Echo: Hello"
