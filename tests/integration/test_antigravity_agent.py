"""Integration tests for google-antigravity Agent workflow using hebras-ai as provider."""
import http.server
import json
import threading

import pytest

from integrations.google_sdk import GoogleSDKConfig, create_agent


class MockHebrasOpenAIServer(http.server.BaseHTTPRequestHandler):
    """Mock HTTP handler emulating hebras-ai /v1/chat/completions endpoint."""

    def do_POST(self):  # pylint: disable=invalid-name
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len > 0:
            self.rfile.read(content_len)

        if self.path == "/v1/chat/completions":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            # SSE chunk 1: role indicator
            chunk1 = {"choices": [{"delta": {"role": "assistant", "content": "Antigravity "}}]}
            # SSE chunk 2: content delta
            chunk2 = {"choices": [{"delta": {"content": "is working locally!"}}]}
            # SSE chunk 3: finish reason
            chunk3 = {"choices": [{"delta": {}, "finish_reason": "stop"}]}

            self.wfile.write(f"data: {json.dumps(chunk1)}\n\n".encode())
            self.wfile.write(f"data: {json.dumps(chunk2)}\n\n".encode())
            self.wfile.write(f"data: {json.dumps(chunk3)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):  # pylint: disable=redefined-builtin
        pass


@pytest.fixture
def mock_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), MockHebrasOpenAIServer)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/v1"
    server.shutdown()
    server.server_close()
    thread.join()


class TestAntigravityAgentIntegration:
    """Tests running Agent workflows connected to a local OpenAI provider."""

    @pytest.mark.asyncio
    async def test_agent_chat_streaming(self, mock_server):
        """Test Agent.chat streams tokens from local hebras-ai endpoint."""
        config = GoogleSDKConfig(
            base_url=mock_server,
            model="Gemini 3.7 Flash",
        )

        async with create_agent(config) as agent:
            response = await agent.chat("Test prompt")
            tokens = [tk async for tk in response]
            full_text = "".join(tokens)

            assert "Antigravity is working locally!" in full_text

