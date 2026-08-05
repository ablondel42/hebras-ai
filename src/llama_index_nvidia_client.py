import os
from dotenv import load_dotenv
from llama_index.llms.nvidia import NVIDIA
from llama_index.core.llms import ChatMessage, MessageRole

load_dotenv()

client = NVIDIA(
  model="nvidia/nemotron-3-ultra-550b-a55b",
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = os.getenv("NVIDIA_API_KEY"),
  is_chat_model=True
)

response = client.chat(
    messages=[
        ChatMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        ChatMessage(role=MessageRole.USER, content="Tell me a Joke about AI")
    ],
)

print(f"\nResponse: {response}\n")
