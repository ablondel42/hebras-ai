"""Unit tests for HebrasLLM CustomLLM class."""
import pytest
from unittest.mock import patch, MagicMock
from integrations.hebras_llm import HebrasLLM
from llama_index.core.llms import LLMMetadata


class TestHebrasLLM:
    def test_metadata(self):
        from llama_index.core.llms.function_calling import FunctionCallingLLM
        llm = HebrasLLM(agent="read", interactive=True)
        assert isinstance(llm, FunctionCallingLLM)
        meta = llm.metadata
        assert isinstance(meta, LLMMetadata)
        assert meta.model_name == "hebras-interactive-read"
        assert meta.is_chat_model is True
        assert meta.is_function_calling_model is True

    def test_complete_sync(self):
        llm = HebrasLLM(agent="read", api_base="http://testserver/v1")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello from hebras!"}}],
            "system_fingerprint": "conv-session-123",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as MockClient:
            mock_client_inst = MagicMock()
            mock_client_inst.post.return_value = mock_resp
            MockClient.return_value.__enter__.return_value = mock_client_inst

            res = llm.complete("Say hello")
            assert res.text == "Hello from hebras!"
            assert llm.conversation_id == "conv-session-123"
            mock_client_inst.post.assert_called_once()
