"""Anthropic SDK wrapper with cost tracking."""

from typing import Any

import anthropic

from ref_validator.errors import LLMError
from ref_validator.models.cost import CostSummary, TokenUsage


class LLMClient:
    """Wrapper around the Anthropic API with structured output via tool_use."""

    def __init__(self, api_key: str, cost_summary: CostSummary | None = None):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is required")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._cost_summary = cost_summary

    async def extract_structured(
        self,
        *,
        model: str,
        system: str,
        user_message: str,
        tool_name: str,
        tool_schema: dict[str, Any],
        max_tokens: int = 8192,
    ) -> dict[str, Any]:
        """Call the LLM with a tool definition and return the structured tool input."""
        tool_def = {
            "name": tool_name,
            "description": f"Extract structured data: {tool_name}",
            "input_schema": tool_schema,
        }
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
                tools=[tool_def],
                tool_choice={"type": "tool", "name": tool_name},
            )
        except anthropic.APIError as e:
            raise LLMError(f"Anthropic API error: {e}") from e

        if self._cost_summary is not None:
            self._cost_summary.add(
                TokenUsage(
                    model=model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
            )

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input  # type: ignore[return-value]

        raise LLMError(f"No tool_use block found in response for {tool_name}")

    async def ask(
        self,
        *,
        model: str,
        system: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> str:
        """Simple text completion."""
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as e:
            raise LLMError(f"Anthropic API error: {e}") from e

        if self._cost_summary is not None:
            self._cost_summary.add(
                TokenUsage(
                    model=model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
            )

        return response.content[0].text if response.content else ""
