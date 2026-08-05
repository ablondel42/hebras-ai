import os
from dotenv import load_dotenv
load_dotenv("dev.env")

from llama_index.llms.nvidia import NVIDIA
from llama_index.core.llms import ChatMessage, MessageRole, ChatResponse


client = NVIDIA(
  model="nvidia/nemotron-3-ultra-550b-a55b",
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = os.getenv("NVIDIA_API_KEY"),
  is_chat_model=True
)


response: ChatResponse = client.chat(
    messages=[
        ChatMessage(
            role=MessageRole.SYSTEM, 
            content="You are a helpful assistant."
        ),
        ChatMessage(
            role=MessageRole.USER, 
            content="Hi there! How are you doing today?"
        )
    ],
)

print(f"\nResponse: {response}\n")
