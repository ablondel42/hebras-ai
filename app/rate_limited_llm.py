"""
rate_limited_llm.py

Run unit tests:
    python rate_limited_llm.py

Run the live NVIDIA test:
    python rate_limited_llm.py --live

Environment:
    NVIDIA_API_KEY=your_api_key
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
import unittest
from typing import Any, Awaitable, Callable

from aiolimiter import AsyncLimiter
from dotenv import load_dotenv
from llama_index.llms.openai_like import OpenAILike


load_dotenv("dev.env")


class RateLimitedLLM:
    """
    Generic async wrapper around a LlamaIndex-compatible model.

    Configuration:
        - 30 requests per 60 seconds.
        - Maximum 1 request executing concurrently.

    The limiter is shared by every request sent through this instance.
    """

    def __init__(
        self,
        model: Any,
        requests_per_minute: int = 30,
        max_concurrent: int = 1,
    ) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be greater than zero")

        if max_concurrent <= 0:
            raise ValueError("max_concurrent must be greater than zero")

        self.model = model

        self.request_limiter = AsyncLimiter(
            max_rate=requests_per_minute,
            time_period=60,
        )

        self.concurrency_limiter = asyncio.Semaphore(max_concurrent)

        self.requests_per_minute = requests_per_minute
        self.max_concurrent = max_concurrent

    async def _execute(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Applies rate and concurrency limits before calling the model.
        """
        async with self.request_limiter:
            async with self.concurrency_limiter:
                method = getattr(self.model, method_name)
                return await method(*args, **kwargs)

    async def acomplete(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> Any:
        """
        Complete a text prompt asynchronously.
        """
        return await self._execute(
            "acomplete",
            prompt,
            **kwargs,
        )

    async def achat(
        self,
        messages: list[Any],
        **kwargs: Any,
    ) -> Any:
        """
        Complete a chat conversation asynchronously.
        """
        return await self._execute(
            "achat",
            messages,
            **kwargs,
        )

    def __getattr__(self, name: str) -> Any:
        """
        Forward non-overridden attributes to the underlying model.

        This is useful for reading model metadata, but calls that need
        rate limiting should go through acomplete() or achat().
        """
        return getattr(self.model, name)


def create_nvidia_model() -> OpenAILike:
    """
    Create the raw LlamaIndex OpenAI-compatible model.

    This model is not rate-limited by itself. It is wrapped by
    create_rate_limited_llm().
    """
    api_key = os.getenv("NVIDIA_API_KEY")

    if not api_key:
        raise RuntimeError(
            "NVIDIA_API_KEY is missing. "
            "Add it to your .env file or export it in your shell."
        )

    return OpenAILike(
        is_chat_model=True,
        is_function_calling_model=True,
        model="nvidia/nemotron-3-ultra-550b-a55b",
        api_base="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
        temperature=0.2,
        max_tokens=2048,
        timeout=120.0,
    )


def create_rate_limited_llm() -> RateLimitedLLM:
    """
    Create the model used by Hebras.

    The important order is:

        1. Create OpenAILike.
        2. Pass it into RateLimitedLLM.
        3. Use the wrapper for all async calls.
    """
    raw_model = create_nvidia_model()

    return RateLimitedLLM(
        model=raw_model,
        requests_per_minute=30,
        max_concurrent=1,
    )


async def run_live_example() -> None:
    """
    Make one real request to the NVIDIA API.
    """
    llm = create_rate_limited_llm()

    response = await llm.acomplete(
        "Explain rate limiting in exactly three short bullet points."
    )

    print("Live response:")
    print(response)


class FakeModel:
    """
    Fake model used by tests.

    It does not call an external API or consume quota.
    """

    def __init__(self, delay: float = 0.02) -> None:
        self.delay = delay
        self.active_requests = 0
        self.max_active_requests = 0
        self.call_count = 0

    async def acomplete(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        self.call_count += 1
        self.active_requests += 1
        self.max_active_requests = max(
            self.max_active_requests,
            self.active_requests,
        )

        try:
            await asyncio.sleep(self.delay)
            return f"fake completion: {prompt}"
        finally:
            self.active_requests -= 1

    async def achat(
        self,
        messages: list[Any],
        **kwargs: Any,
    ) -> str:
        self.call_count += 1
        self.active_requests += 1
        self.max_active_requests = max(
            self.max_active_requests,
            self.active_requests,
        )

        try:
            await asyncio.sleep(self.delay)
            return "fake chat completion"
        finally:
            self.active_requests -= 1


class RateLimitedLLMTests(unittest.IsolatedAsyncioTestCase):
    """
    Unit tests for the wrapper.

    These tests use FakeModel and never call NVIDIA.
    """

    async def test_acomplete_delegates_to_underlying_model(self) -> None:
        fake_model = FakeModel()
        llm = RateLimitedLLM(
            model=fake_model,
            requests_per_minute=30,
            max_concurrent=1,
        )

        response = await llm.acomplete("hello")

        self.assertEqual(
            response,
            "fake completion: hello",
        )
        self.assertEqual(fake_model.call_count, 1)

    async def test_achat_delegates_to_underlying_model(self) -> None:
        fake_model = FakeModel()
        llm = RateLimitedLLM(
            model=fake_model,
            requests_per_minute=30,
            max_concurrent=1,
        )

        response = await llm.achat(
            [
                {
                    "role": "user",
                    "content": "hello",
                }
            ]
        )

        self.assertEqual(
            response,
            "fake chat completion",
        )
        self.assertEqual(fake_model.call_count, 1)

    async def test_concurrency_limit_is_respected(self) -> None:
        fake_model = FakeModel(delay=0.05)

        llm = RateLimitedLLM(
            model=fake_model,
            requests_per_minute=30,
            max_concurrent=1,
        )

        await asyncio.gather(
            llm.acomplete("one"),
            llm.acomplete("two"),
            llm.acomplete("three"),
            llm.acomplete("four"),
        )

        self.assertEqual(fake_model.call_count, 4)

        self.assertEqual(
            fake_model.max_active_requests,
            1,
        )

    async def test_higher_concurrency_allows_more_parallel_requests(self) -> None:
        fake_model = FakeModel(delay=0.05)

        llm = RateLimitedLLM(
            model=fake_model,
            requests_per_minute=30,
            max_concurrent=2,
        )

        await asyncio.gather(
            llm.acomplete("one"),
            llm.acomplete("two"),
            llm.acomplete("three"),
            llm.acomplete("four"),
        )

        self.assertEqual(fake_model.call_count, 4)

        self.assertLessEqual(
            fake_model.max_active_requests,
            2,
        )

        self.assertGreaterEqual(
            fake_model.max_active_requests,
            2,
        )

    async def test_rate_limiter_configuration(self) -> None:
        fake_model = FakeModel()

        llm = RateLimitedLLM(
            model=fake_model,
            requests_per_minute=30,
            max_concurrent=1,
        )

        self.assertEqual(
            llm.request_limiter.max_rate,
            30,
        )

        self.assertEqual(
            llm.request_limiter.time_period,
            60,
        )

        self.assertEqual(
            llm.requests_per_minute,
            30,
        )

        self.assertEqual(
            llm.max_concurrent,
            1,
        )

    async def test_invalid_configuration_is_rejected(self) -> None:
        fake_model = FakeModel()

        with self.assertRaises(ValueError):
            RateLimitedLLM(
                model=fake_model,
                requests_per_minute=0,
            )

        with self.assertRaises(ValueError):
            RateLimitedLLM(
                model=fake_model,
                requests_per_minute=30,
                max_concurrent=0,
            )

    async def test_requests_are_not_run_in_parallel_with_one_slot(self) -> None:
        fake_model = FakeModel(delay=0.05)

        llm = RateLimitedLLM(
            model=fake_model,
            requests_per_minute=30,
            max_concurrent=1,
        )

        start = time.perf_counter()

        await asyncio.gather(
            llm.acomplete("one"),
            llm.acomplete("two"),
            llm.acomplete("three"),
        )

        elapsed = time.perf_counter() - start

        self.assertGreaterEqual(
            elapsed,
            0.14,
        )


def run_tests() -> bool:
    """
    Run all unit tests and return whether they succeeded.
    """
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        RateLimitedLLMTests
    )

    result = unittest.TextTestRunner(
        verbosity=2,
    ).run(suite)

    return result.wasSuccessful()


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one real request against the NVIDIA API.",
    )

    args = parser.parse_args()

    tests_passed = run_tests()

    if not tests_passed:
        raise SystemExit(1)

    if args.live:
        asyncio.run(run_live_example())


if __name__ == "__main__":
    main()