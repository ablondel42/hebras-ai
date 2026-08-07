import asyncio
import os
from dotenv import load_dotenv
load_dotenv("dev.env")

from llama_index.llms.nvidia import NVIDIA
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.prompts import PromptTemplate
from llama_index.core.agent import ReActAgent, FunctionAgent
from llama_index.core.workflow import Context

from aiolimiter import AsyncLimiter


class RateLimitedModel:
    def __init__(self, model, requests_per_minute: int, max_concurrent: int = 1):
        self.model = model
        self.request_limiter = AsyncLimiter(requests_per_minute, 30)
        self.concurrency = asyncio.Semaphore(max_concurrent)

    async def acomplete(self, request):
        async with self.request_limiter:
            async with self.concurrency:
                return await self.model.acomplete(request)

rate_limiter = RateLimitedModel(
    model=None,  # This will be set to the actual model instance later
    requests_per_minute=30,  # Set your desired rate limit here
    max_concurrent=1  # Set the maximum number of concurrent requests
)

llm = OpenAILike(
    is_chat_model=True,
    model="nvidia/nemotron-3-ultra-550b-a55b",
    api_base = "https://integrate.api.nvidia.com/v1",
    api_key = os.getenv("NVIDIA_API_KEY"),
)


response = llm.chat(
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

# prompt = PromptTemplate("Random fact about {topic}.")
# gen = llm.stream(prompt, topic="AI")
# print("\n\n--- Streaming response:\n")
# for token in gen:
#     print(token, end="", flush=True)

# print("\n\n--- Done streaming response.\n")

# def multiply(a: float, b: float) -> float:
#     """Multiply two numbers and returns the product"""
#     return a * b


# def add(a: float, b: float) -> float:
#     """Add two numbers and returns the sum"""
#     return a + b



# workflow = ReActAgent(
#     tools=[multiply, add],
#     llm=llm,
#     system_prompt="You are an agent that can perform basic mathematical operations using tools.",
# )

# async def main():
#     response = await workflow.run(user_msg="What is 20+(2*4)?")
#     print(response)


# if __name__ == "__main__":
#     import asyncio

#     asyncio.run(main())

