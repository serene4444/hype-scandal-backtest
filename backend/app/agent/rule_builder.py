"""Plain-English rule builder: a small tool-calling agent.

Claude reads a rule like "buy Palantir after a 7% weekly drop", maps it onto a
backtester template by calling our own tools (list_strategies, run_backtest,
get_metrics, compare_to_monkeys), and explains whether the rule beat
buy-and-hold and the random monkeys. The loop is written out by hand so every
tool call is recorded and can be shown to the user next to the answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .tools import TOOLS, Toolbox, ToolError

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
MAX_TURNS = 8
EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """\
You turn a plain-English trading rule into a backtest on the Hype vs. Scandal backtester, then explain \
the result to someone who is not a finance expert.

The backtester supports only Meta (META) and Palantir (PLTR) and a small set of rule templates. Start by \
calling list_strategies, then map the user's rule onto the closest template and parameters. Usual \
translations: "weekly" means 5 trading days, "monthly" 21, and 7% means 0.07. When the user leaves \
something out, use the defaults: start on the first date the stock has data, $1,000, a $1 fee per trade, \
and the template's own exit rule. If no template can express the rule (another stock, short selling, \
news or earnings signals, position sizing), say so plainly. If a close approximation exists, run it and \
call it an approximation.

After run_backtest succeeds, call get_metrics and compare_to_monkeys on its backtest_id before you \
answer; you can call those two in parallel. If a tool returns an error, correct the input and try again; \
if it keeps failing, explain what went wrong instead of guessing numbers.

Write the answer in plain English, under 200 words, with no tables or headings:
- How you read the rule: template, parameters, date range, and the exit rule you assumed.
- Whether it beat buy-and-hold: both ending values, and each one's biggest drop.
- Whether it beat the monkeys: the share of random traders with the same number of trades that it beat, \
and what that says about skill versus luck. Beating fewer than about 95% is not strong evidence of skill.
- One honest caveat, such as few trades, a single stock, or one lucky stretch.
Only use numbers that came back from the tools. End with: "Educational simulation, not financial advice."\
"""


class AgentError(Exception):
    """The agent could not produce an answer."""


@dataclass
class ToolStep:
    tool: str
    input: dict[str, Any]
    output: Any
    is_error: bool = False


@dataclass
class AgentResult:
    answer: str
    steps: list[ToolStep] = field(default_factory=list)
    backtest_ids: list[str] = field(default_factory=list)
    refused: bool = False


def _text(content: list[Any]) -> str:
    return "\n\n".join(block.text for block in content if block.type == "text").strip()


class RuleBuilderAgent:
    def __init__(self, client: Any, toolbox: Toolbox, model: str = MODEL, max_turns: int = MAX_TURNS) -> None:
        self.client = client
        self.toolbox = toolbox
        self.model = model
        self.max_turns = max_turns

    def _create(self, messages: list[dict[str, Any]]) -> Any:
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": EFFORT},
            # If a safety classifier declines, the API retries on a fallback model inside the same call.
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

    def _run_tool(self, block: Any) -> tuple[ToolStep, dict[str, Any]]:
        args = block.input if isinstance(block.input, dict) else {}
        try:
            output: Any = self.toolbox.call(block.name, args)
            is_error = False
        except ToolError as exc:
            output, is_error = {"error": str(exc)}, True
        step = ToolStep(tool=block.name, input=args, output=output, is_error=is_error)
        result = {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": json.dumps(output, default=str),
            "is_error": is_error,
        }
        return step, result

    def run(self, prompt: str) -> AgentResult:
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        steps: list[ToolStep] = []

        for _ in range(self.max_turns):
            response = self._create(messages)
            # Append the full content (thinking blocks included) so the history stays valid.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "tool_use":
                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        step, result = self._run_tool(block)
                        steps.append(step)
                        results.append(result)
                # Every result for this turn goes back in one user message.
                messages.append({"role": "user", "content": results})
                continue
            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason == "refusal":
                return AgentResult(
                    answer=_text(response.content) or "Claude declined to answer this request.",
                    steps=steps,
                    backtest_ids=list(self.toolbox.backtest_ids),
                    refused=True,
                )
            if response.stop_reason in ("end_turn", "stop_sequence"):
                answer = _text(response.content)
                if not answer:
                    raise AgentError("Claude finished without writing an answer")
                return AgentResult(answer=answer, steps=steps, backtest_ids=list(self.toolbox.backtest_ids))
            raise AgentError(f"Claude stopped early ({response.stop_reason})")

        raise AgentError(f"No answer after {self.max_turns} turns")
