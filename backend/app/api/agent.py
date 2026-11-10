"""Plain-English rule builder endpoint (v3): Claude turns a rule into backtests and explains the result."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.agent.rule_builder import AgentError, RuleBuilderAgent
from app.agent.tools import Toolbox
from app.api.backtests import PriceLoader, get_price_loader

router = APIRouter(prefix="/agent", tags=["agent"])


@lru_cache(maxsize=1)
def _default_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def get_claude_client() -> Any:
    """Dependency so tests can swap in a fake client."""
    try:
        return _default_client()
    except anthropic.AnthropicError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Claude API credentials are not configured") from exc


class RuleRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500, examples=["buy Palantir after a 7% weekly drop"])


class StepOut(BaseModel):
    tool: str
    input: dict[str, Any]
    output: Any
    is_error: bool


class RuleResponse(BaseModel):
    answer: str
    steps: list[StepOut]
    backtest_ids: list[str]
    refused: bool = False


@router.post("/rule", response_model=RuleResponse)
def build_rule(
    body: RuleRequest,
    client: Any = Depends(get_claude_client),
    load: PriceLoader = Depends(get_price_loader),
) -> RuleResponse:
    agent = RuleBuilderAgent(client, Toolbox(load))
    try:
        result = agent.run(body.prompt)
    except AgentError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except anthropic.AuthenticationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Claude API credentials were rejected") from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Claude is busy, try again shortly") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Claude API error ({exc.status_code})") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not reach the Claude API") from exc
    return RuleResponse(
        answer=result.answer,
        steps=[StepOut(**vars(step)) for step in result.steps],
        backtest_ids=result.backtest_ids,
        refused=result.refused,
    )
