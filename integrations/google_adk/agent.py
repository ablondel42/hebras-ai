"""Google ADK agent definition for ADK CLI discovery."""
from integrations.google_adk.google_adk_integration import create_agent


def get_current_time(city: str) -> str:
    """Get the current time in a specified city."""
    return f"The current time in {city} is 12:00 PM."


root_agent = create_agent(
    base_url="http://localhost:8000/v1",
    model="Gemini 3.7 Flash",
    name="root_agent",
    description="Tells the current time in a specified city.",
    instruction="You are a helpful assistant that tells the current time in cities. Use the 'get_current_time' tool for this purpose.",
    tools=[get_current_time],
)

