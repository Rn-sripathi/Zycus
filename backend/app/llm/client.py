"""Thin async wrapper around the OpenAI client.

Everything that can go wrong with a model call -- timeouts, rate limits, a
response that isn't valid JSON -- is handled here, so the three pipeline steps
that use the model contain business logic only.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.config import get_settings

logger = logging.getLogger(__name__)

_RETRYABLE = (APITimeoutError, APIConnectionError, RateLimitError)


class LLMError(RuntimeError):
    """Raised when a model call cannot be completed or parsed."""


class LLMClient:
    """Issues structured-output calls and returns parsed dictionaries."""

    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        settings = get_settings()
        if not settings.llm_enabled and client is None:
            raise LLMError("OPENAI_API_KEY is not configured")

        self._settings = settings
        self._client = client or AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,  # retries are handled below so backoff stays visible in logs
        )

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Call the model and return its response parsed as a dictionary.

        Uses structured outputs so the model cannot return prose where the
        pipeline expects fields.
        """
        last_error: Exception | None = None

        for attempt in range(self._settings.llm_max_retries + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self._settings.openai_model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "schema": schema,
                            "strict": True,
                        },
                    },
                )
            except _RETRYABLE as exc:
                last_error = exc
                if attempt < self._settings.llm_max_retries:
                    delay = 2**attempt
                    logger.warning(
                        "%s on %s (attempt %d), retrying in %ss",
                        type(exc).__name__,
                        schema_name,
                        attempt + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise LLMError(f"{schema_name} failed after retries: {exc}") from exc
            except Exception as exc:  # noqa: BLE001 - surfaced as LLMError to the caller
                raise LLMError(f"{schema_name} call failed: {exc}") from exc

            content = response.choices[0].message.content
            if not content:
                raise LLMError(f"{schema_name} returned an empty response")

            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise LLMError(f"{schema_name} returned invalid JSON: {exc}") from exc

        raise LLMError(f"{schema_name} failed: {last_error}")
