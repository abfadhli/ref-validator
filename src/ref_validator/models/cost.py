"""Cost tracking models."""

from pydantic import BaseModel, Field

# Pricing per million tokens (USD) as of early 2025
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_million, output_per_million)
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
    "claude-opus-4-6": (15.0, 75.0),
}


class TokenUsage(BaseModel):
    """Token usage for a single LLM call."""

    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def estimated_cost_usd(self) -> float:
        pricing = MODEL_PRICING.get(self.model)
        if not pricing:
            return 0.0
        input_cost = (self.input_tokens / 1_000_000) * pricing[0]
        output_cost = (self.output_tokens / 1_000_000) * pricing[1]
        return input_cost + output_cost


class CostSummary(BaseModel):
    """Aggregated cost across all LLM calls."""

    usages: list[TokenUsage] = Field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(u.input_tokens for u in self.usages)

    @property
    def total_output_tokens(self) -> int:
        return sum(u.output_tokens for u in self.usages)

    @property
    def total_estimated_cost_usd(self) -> float:
        return sum(u.estimated_cost_usd for u in self.usages)

    def add(self, usage: TokenUsage) -> None:
        self.usages.append(usage)
