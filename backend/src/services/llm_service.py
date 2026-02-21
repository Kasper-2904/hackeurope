"""LLMService — thin async wrapper around the Anthropic SDK."""

import json
from typing import Any

import anthropic

from src.config import get_settings


class LLMService:
    """Async wrapper around the Anthropic Python SDK for OA and Reviewer calls."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.default_llm_model
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        *,
        system: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Send a single-turn message and return the text response."""
        response = await self.client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            temperature=temperature,
        )
        # Extract text from the response content blocks
        return "".join(
            block.text for block in response.content if block.type == "text"
        )

    async def complete_json(
        self,
        *,
        system: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Send a message and parse the response as JSON.

        The system prompt should instruct the model to respond in JSON.
        """
        raw = await self.complete(
            system=system,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # Strip markdown fences if present (only opening/closing lines)
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:]  # Remove opening fence (e.g. ```json)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # Remove closing fence
            text = "\n".join(lines)
        return json.loads(text)


# Module-level singleton
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get the global LLMService instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
