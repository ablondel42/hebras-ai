"""Unit test for LlamaIndex integration."""
import pytest

pytest.importorskip("llama_index.core")

from unittest.mock import MagicMock, patch

from llama_index.core.llms import CompletionResponse

from integrations.llama_index import HebrasLLM, LlamaIndexConfig


def test_llama_index_complete():
    """Verify HebrasLLM executes completion against chat endpoint."""
    llm = HebrasLLM(base_url="http://localhost:8000/v1", model_name="Gemini 3.7 Flash")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Hello from LlamaIndex!"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        response = llm.complete("Hi")

        assert isinstance(response, CompletionResponse)
        assert response.text == "Hello from LlamaIndex!"
        mock_client.post.assert_called_once_with(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "Gemini 3.7 Flash",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )
