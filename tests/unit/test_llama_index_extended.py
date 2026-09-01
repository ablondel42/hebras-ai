import pytest
pytest.importorskip("llama_index.core")

from unittest.mock import MagicMock, patch

from integrations.hebras_llm import HebrasLLM


class TestHebrasLLMExtended:
    def test_build_payload_defaults(self):
        llm = HebrasLLM(agent="default", interactive=True)
        payload = llm._build_payload("Hello")
        assert payload["model"] == "Gemini 3.7 Flash"
        assert payload["agent"] == "default"
        assert payload["reflection"] == "high"
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]
        assert payload["interactive"] is True
        assert payload["dangerously_skip_permissions"] is False
        assert "mode" not in payload

    def test_build_payload_with_mode_and_permissions(self):
        llm = HebrasLLM(agent="code_writer", model_name="Claude Sonnet 4.6", mode="plan", dangerously_skip_permissions=True)
        payload = llm._build_payload("Draft code")
        assert payload["model"] == "Claude Sonnet 4.6"
        assert payload["agent"] == "code_writer"
        assert payload["mode"] == "plan"
        assert payload["dangerously_skip_permissions"] is True

    def test_prepare_chat_with_tools(self):
        llm = HebrasLLM()
        res = llm._prepare_chat_with_tools(tools=[], user_msg="Test user msg")
        assert "messages" in res
        assert len(res["messages"]) == 1
        assert res["messages"][0].content == "Test user msg"

    def test_get_tool_calls_from_response_stub(self):
        llm = HebrasLLM()
        assert llm.get_tool_calls_from_response(response=None) == []
        with pytest.raises(ValueError, match="No tool calls found"):
            llm.get_tool_calls_from_response(response=None, error_on_no_tool_call=True)

    def test_stream_complete_fallback_on_error(self):
        llm = HebrasLLM(api_base="http://testserver/v1")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Fallback completion text"}}],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as MockClient:
            mock_inst = MagicMock()
            mock_inst.stream.side_effect = Exception("Stream connection failed")
            mock_inst.post.return_value = mock_resp
            MockClient.return_value.__enter__.return_value = mock_inst

            chunks = list(llm.stream_complete("Test prompt"))
            assert len(chunks) == 1
            assert chunks[0].text == "Fallback completion text"

    @pytest.mark.asyncio
    async def test_acomplete(self):
        from unittest.mock import AsyncMock
        llm = HebrasLLM(api_base="http://testserver/v1")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Async response text"}}],
            "system_fingerprint": "async-conv-123",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_inst = MagicMock()
            mock_inst.post = AsyncMock(return_value=mock_resp)
            MockAsyncClient.return_value.__aenter__.return_value = mock_inst

            res = await llm.acomplete("Async test")
            assert res.text == "Async response text"
            assert llm.conversation_id == "async-conv-123"
