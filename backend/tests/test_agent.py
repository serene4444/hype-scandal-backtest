"""Rule-builder agent tests, driven by a scripted fake Claude client (no network, no API key)."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.agent.rule_builder import MODEL, RuleBuilderAgent
from app.agent.tools import TOOLS, Toolbox
from app.api import agent as agent_api
from app.api import backtests
from app.main import app
from tests.conftest import make_prices

RUN_ARGS = {
    "ticker": "PLTR",
    "strategy": "buy_the_dip",
    "params": {"drop_pct": 0.07, "lookback": 5},
    "start_date": "2023-01-02",
}


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool_use(id_, name, args):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=args)


def reply(stop_reason, *blocks):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def last_results(messages):
    return {r["tool_use_id"]: r for r in messages[-1]["content"]}


class FakeClient:
    """Plays a script: each entry is a function from the messages so far to the next response."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.script.pop(0)(kwargs["messages"])


def happy_script():
    def ask_metrics(messages):
        backtest_id = json.loads(last_results(messages)["run"]["content"])["backtest_id"]
        return reply(
            "tool_use",
            tool_use("m", "get_metrics", {"backtest_id": backtest_id}),
            tool_use("k", "compare_to_monkeys", {"backtest_id": backtest_id, "n_monkeys": 50}),
        )

    def answer(messages):
        results = last_results(messages)
        share = json.loads(results["k"]["content"])["share_beaten"]
        return reply("end_turn", text(f"It beat {share:.0%} of monkeys."))

    return [
        lambda m: reply("tool_use", text("Checking templates."), tool_use("ls", "list_strategies", {}),
                        tool_use("run", "run_backtest", RUN_ARGS)),
        ask_metrics,
        answer,
    ]


@pytest.fixture
def prices():
    rng = np.random.default_rng(1)
    return make_prices(100 * np.cumprod(1 + rng.normal(0, 0.03, 300)), start="2023-01-02")


@pytest.fixture
def toolbox(prices):
    backtests.reset_store()
    return Toolbox(lambda ticker, start, end: prices[prices.index >= str(start)])


def test_agent_calls_tools_and_answers(toolbox):
    client = FakeClient(happy_script())
    result = RuleBuilderAgent(client, toolbox).run("buy Palantir after a 7% weekly drop")

    assert [s.tool for s in result.steps] == ["list_strategies", "run_backtest", "get_metrics", "compare_to_monkeys"]
    assert not any(s.is_error for s in result.steps)
    assert result.answer.startswith("It beat") and result.answer.endswith("of monkeys.")
    assert len(result.backtest_ids) == 1

    metrics = result.steps[2].output
    assert metrics["strategy_metrics"]["trade_count"] > 0
    assert metrics["beat_buy_and_hold"] == (
        metrics["strategy_metrics"]["ending_value"] > metrics["buy_and_hold_metrics"]["ending_value"]
    )
    assert 0 <= result.steps[3].output["share_beaten"] <= 1


def test_request_shape(toolbox):
    client = FakeClient(happy_script())
    RuleBuilderAgent(client, toolbox).run("buy Palantir after a 7% weekly drop")
    first, second = client.calls[0], client.calls[1]
    assert first["model"] == MODEL
    assert first["fallbacks"] == "default"
    assert {t["name"] for t in first["tools"]} == {"list_strategies", "run_backtest", "get_metrics", "compare_to_monkeys"}
    # Both parallel tool results go back together in a single user message.
    assert second["messages"][-1]["role"] == "user"
    assert len(second["messages"][-1]["content"]) == 2


def test_tool_errors_go_back_to_claude(toolbox):
    bad = {**RUN_ARGS, "params": {"drop_pct": 7}}  # 7 instead of 0.07

    def retry(messages):
        result = last_results(messages)["bad"]
        assert result["is_error"] and "drop_pct" in result["content"]
        return reply("tool_use", tool_use("ok", "run_backtest", RUN_ARGS))

    client = FakeClient([
        lambda m: reply("tool_use", tool_use("bad", "run_backtest", bad)),
        retry,
        lambda m: reply("end_turn", text("Done.")),
    ])
    result = RuleBuilderAgent(client, toolbox).run("buy PLTR after a 7% drop")
    assert [s.is_error for s in result.steps] == [True, False]


@pytest.mark.parametrize(
    "name, args, message",
    [
        ("get_metrics", {"backtest_id": "nope"}, "not found"),
        ("run_backtest", {**RUN_ARGS, "ticker": "TSLA"}, "ticker"),
        ("run_backtest", {**RUN_ARGS, "start_date": "2010-01-01"}, "data starts"),
        ("delete_everything", {}, "Unknown tool"),
    ],
)
def test_toolbox_errors_are_readable(toolbox, name, args, message):
    from app.agent.tools import ToolError

    with pytest.raises(ToolError, match=message):
        toolbox.call(name, args)


def test_tool_names_match_handlers(toolbox):
    for tool in TOOLS:
        assert hasattr(toolbox, f"_{tool['name']}")


def test_refusal(toolbox):
    client = FakeClient([lambda m: reply("refusal")])
    result = RuleBuilderAgent(client, toolbox).run("something")
    assert result.refused and result.answer


@pytest.fixture
def api(prices):
    backtests.reset_store()
    app.dependency_overrides[backtests.get_price_loader] = lambda: (
        lambda ticker, start, end: prices[prices.index >= str(start)]
    )
    yield app
    app.dependency_overrides.clear()


def test_endpoint(api):
    api.dependency_overrides[agent_api.get_claude_client] = lambda: FakeClient(happy_script())
    response = TestClient(api).post("/agent/rule", json={"prompt": "buy Palantir after a 7% weekly drop"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["steps"]) == 4 and body["backtest_ids"]
    # The run the agent made is a normal backtest the results screen can open.
    assert TestClient(api).get(f"/backtests/{body['backtest_ids'][0]}").status_code == 200


def test_endpoint_runaway_loop(api):
    looping = [lambda m: reply("tool_use", tool_use(f"t{i}", "list_strategies", {})) for i in range(20)]
    api.dependency_overrides[agent_api.get_claude_client] = lambda: FakeClient(looping)
    response = TestClient(api).post("/agent/rule", json={"prompt": "loop forever"})
    assert response.status_code == 502


def test_endpoint_validates_prompt(api):
    api.dependency_overrides[agent_api.get_claude_client] = lambda: FakeClient([])
    assert TestClient(api).post("/agent/rule", json={"prompt": "x" * 501}).status_code == 422
