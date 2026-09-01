"""Unit test for Google Antigravity SDK integration."""
from google.antigravity import Agent, LocalOpenAIAgentConfig

from integrations.google_sdk import GoogleSDKConfig, create_agent


def test_google_sdk_integration():
    """Verify GoogleSDKConfig builds valid Agent instance."""
    config = GoogleSDKConfig(
        base_url="http://localhost:8000/v1",
        model="Gemini 3.7 Flash",
        system_instructions="You are a helpful assistant.",
    )
    agent = create_agent(config)

    assert isinstance(agent, Agent)
    assert isinstance(agent._config, LocalOpenAIAgentConfig)
    assert agent._config.base_url == "http://localhost:8000/v1"
    assert agent._config.model == "Gemini 3.7 Flash"
    assert agent._config.system_instructions == "You are a helpful assistant."
