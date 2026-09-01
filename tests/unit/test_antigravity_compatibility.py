"""Unit tests for google-antigravity SDK compatibility with hebras-ai."""
from google.antigravity import LocalOpenAIAgentConfig
from google.antigravity.hooks import policy

from backend.routes.chat import _extract_prompt_and_system
from backend.types import ChatCompletionRequest, ChatMessage


class TestAntigravityCompatibility:
    """Tests verifying request schema and parsing compatibility for google-antigravity SDK."""

    def test_local_openai_agent_config_setup(self):
        """Test configuring LocalOpenAIAgentConfig pointing to hebras-ai."""
        config = LocalOpenAIAgentConfig(
            base_url="http://localhost:8000/v1",
            model="Gemini 3.7 Flash",
            policies=[policy.allow_all()],
        )
        assert config.base_url == "http://localhost:8000/v1"
        assert config.model == "Gemini 3.7 Flash"
        assert len(config.policies) == 1

    def test_chat_completion_request_with_tools(self):
        """Test ChatCompletionRequest accepts OpenAI tool calling fields from Antigravity harness."""
        payload = {
            "model": "Gemini 3.7 Flash",
            "messages": [
                {"role": "system", "content": "You are a calculator."},
                {"role": "user", "content": "Add 2 and 2"},
            ],
            "stream": True,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "add",
                        "description": "Add two numbers",
                        "parameters": {
                            "type": "object",
                            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                        },
                    },
                }
            ],
            "tool_choice": "auto",
            "extra_harness_field": "some_value",
        }

        req = ChatCompletionRequest.model_validate(payload)
        assert req.model == "Gemini 3.7 Flash"
        assert req.stream is True
        assert req.tools is not None
        assert len(req.tools) == 1
        assert req.tools[0]["function"]["name"] == "add"
        assert req.tool_choice == "auto"

    def test_extract_prompt_and_system_single_user(self):
        """Test extracting single user message and system instructions."""
        req = ChatCompletionRequest(
            messages=[
                ChatMessage(role="system", content="System instruction text"),
                ChatMessage(role="user", content="User question"),
            ]
        )
        prompt, sys_msg = _extract_prompt_and_system(req)
        assert sys_msg == "System instruction text"
        assert "[System Instructions]\nSystem instruction text" in prompt
        assert "[User Request]\nUser question" in prompt

    def test_extract_prompt_and_system_tool_response(self):
        """Test extracting dialogue turns including tool responses."""
        req = ChatCompletionRequest(
            messages=[
                ChatMessage(role="system", content="Math agent"),
                ChatMessage(role="user", content="Add 10 and 20"),
                ChatMessage(role="assistant", content=None, tool_calls=[{"function": {"name": "add"}}]),
                ChatMessage(role="tool", content="30", tool_call_id="call_1"),
            ]
        )
        prompt, sys_msg = _extract_prompt_and_system(req)
        assert sys_msg == "Math agent"
        assert "Add 10 and 20" in prompt
        assert "[Tool Response]: 30" in prompt
