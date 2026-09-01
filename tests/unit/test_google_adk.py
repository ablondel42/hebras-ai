"""Unit test for Google ADK integration."""
from google.adk.agents.llm_agent import Agent
from google.adk.cli.utils.agent_loader import AgentLoader, is_single_agent_directory
from google.adk.labs.openai import OpenAILlm

from integrations.google_adk import GoogleADKConfig, create_agent


def test_google_adk_create_agent():
    """Verify create_agent returns configured Google ADK Agent ready to run against hebras-ai."""
    def get_current_time(city: str) -> str:
        return f"The current time in {city} is 12:00 PM"

    config = GoogleADKConfig(
        base_url="http://localhost:8000/v1",
        model="Gemini 3.7 Flash",
        name="root_agent",
        description="Tells the current time in a specified city.",
        instruction="You are a helpful assistant that tells the current time in cities. Use the 'get_current_time' tool for this purpose.",
        tools=[get_current_time],
    )
    agent = create_agent(config)

    assert isinstance(agent, Agent)
    assert agent.name == "root_agent"
    assert isinstance(agent.model, OpenAILlm)
    assert agent.model.model == "Gemini 3.7 Flash"
    assert "8000" in str(agent.model.client.base_url)
    assert agent.description == "Tells the current time in a specified city."
    assert agent.instruction == "You are a helpful assistant that tells the current time in cities. Use the 'get_current_time' tool for this purpose."
    assert agent.tools == [get_current_time]


def test_google_adk_create_agent_kwargs():
    """Verify create_agent returns configured Agent from direct kwargs."""
    def get_current_time(city: str) -> str:
        return "12:00 PM"

    agent = create_agent(
        base_url="http://localhost:8000/v1",
        model="Gemini 3.7 Flash",
        name="root_agent",
        description="Tells the current time in a specified city.",
        instruction="You are a helpful assistant that tells the current time in cities. Use the 'get_current_time' tool for this purpose.",
        tools=[get_current_time],
    )

    assert isinstance(agent, Agent)
    assert agent.name == "root_agent"
    assert isinstance(agent.model, OpenAILlm)
    assert agent.model.model == "Gemini 3.7 Flash"
    assert "8000" in str(agent.model.client.base_url)
    assert agent.description == "Tells the current time in a specified city."
    assert agent.instruction == "You are a helpful assistant that tells the current time in cities. Use the 'get_current_time' tool for this purpose."


def test_google_adk_agent_loader_discovery():
    """Verify ADK AgentLoader discovers root_agent in integrations/google_adk."""
    agent_dir = "/workspaces/hebras-ai/integrations/google_adk"
    assert is_single_agent_directory(agent_dir) is True

    loader = AgentLoader(agent_dir)
    assert loader.is_single_agent is True
    agents = loader.list_agents()
    assert len(agents) == 1

    loaded = loader.load_agent(agents[0])
    assert isinstance(loaded, Agent)
    assert loaded.name == "root_agent"
    assert isinstance(loaded.model, OpenAILlm)
    assert len(loaded.tools) == 1




