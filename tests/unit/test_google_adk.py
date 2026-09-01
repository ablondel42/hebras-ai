"""Unit test for Google ADK integration."""
from unittest.mock import MagicMock, patch

from integrations.google_adk import GoogleADKAgent, GoogleADKConfig


def test_google_adk_run():
    """Verify GoogleADKAgent executes synchronous run against chat endpoint."""
    config = GoogleADKConfig(
        base_url="http://localhost:8000/v1",
        model="Gemini 3.7 Flash",
        system_instruction="You are a helpful assistant.",
    )
    agent = GoogleADKAgent(config)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Hello from Google ADK!"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        response = agent.run("Hi")

        assert response == "Hello from Google ADK!"
        mock_client.post.assert_called_once_with(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "Gemini 3.7 Flash",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hi"},
                ],
            },
        )
