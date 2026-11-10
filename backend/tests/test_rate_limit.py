from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import store
from app.api import agent as agent_api
from app.main import app
from tests.test_agent import FakeClient, reply, text

PROMPT = {"prompt": "buy Palantir after a 7% weekly drop"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AGENT_RULES_PER_HOUR", "2")
    monkeypatch.setenv("AGENT_RULES_PER_DAY", "3")
    monkeypatch.setenv("CLIENT_IP_HEADER", "x-forwarded-for")
    # Each call answers straight away without tools, so only the limiter is being tested.
    app.dependency_overrides[agent_api.get_claude_client] = lambda: FakeClient([lambda m: reply("end_turn", text("ok"))])
    yield TestClient(app)
    app.dependency_overrides.clear()


def post(client, ip):
    return client.post("/agent/rule", json=PROMPT, headers={"X-Forwarded-For": ip})


def test_per_visitor_hourly_limit(client):
    assert post(client, "1.1.1.1").status_code == 200
    assert post(client, "1.1.1.1").status_code == 200
    blocked = post(client, "1.1.1.1")
    assert blocked.status_code == 429
    assert "this hour" in blocked.json()["detail"]
    assert 0 < int(blocked.headers["Retry-After"]) <= 3600
    # Another visitor is not affected.
    assert post(client, "2.2.2.2").status_code == 200


def test_site_wide_daily_cap(client):
    for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
        assert post(client, ip).status_code == 200
    blocked = post(client, "4.4.4.4")
    assert blocked.status_code == 429
    assert "whole site" in blocked.json()["detail"]


def test_spoofed_forwarded_for_uses_last_address(client):
    """Visitors can put anything at the front of X-Forwarded-For; the proxy's last entry is used."""
    assert post(client, "9.9.9.9, 1.1.1.1").status_code == 200
    assert post(client, "8.8.8.8, 1.1.1.1").status_code == 200
    assert post(client, "7.7.7.7, 1.1.1.1").status_code == 429


def test_old_calls_stop_counting(client):
    two_hours_ago = store.utc_now() - timedelta(hours=2)
    from app.api.rate_limit import client_key

    class FakeRequest:
        headers = {"x-forwarded-for": "1.1.1.1"}
        client = None

    key = client_key(FakeRequest())
    store.record_agent_call(key, two_hours_ago)
    store.record_agent_call(key, two_hours_ago)
    assert post(client, "1.1.1.1").status_code == 200


def test_invalid_prompt_does_not_use_a_run(client):
    assert client.post("/agent/rule", json={"prompt": "x"}, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 422
    assert store.agent_calls_since(datetime(2000, 1, 1))[0] == 0


def test_raw_ip_is_never_stored(client):
    post(client, "1.1.1.1")
    from sqlalchemy import select

    from app.db import agent_calls, get_engine

    with get_engine().connect() as conn:
        stored = conn.execute(select(agent_calls.c.client)).scalar()
    assert "1.1.1.1" not in stored and len(stored) == 32


def test_rejected_calls_are_not_counted(client):
    for _ in range(4):
        post(client, "1.1.1.1")
    assert store.agent_calls_since(datetime(2000, 1, 1))[0] == 2


def test_events_older_than_two_days_are_deleted():
    store.record_agent_call("someone", store.utc_now() - timedelta(days=3))
    store.record_agent_call("someone", store.utc_now())
    assert store.agent_calls_since(datetime(2000, 1, 1))[0] == 1


def test_proxy_hops_picks_the_right_address(monkeypatch):
    from app.api.rate_limit import client_key

    class FakeRequest:
        headers = {"x-forwarded-for": "6.6.6.6, 1.1.1.1, 10.0.0.1"}
        client = None

    class Direct(FakeRequest):
        headers = {"x-forwarded-for": "1.1.1.1"}

    monkeypatch.setenv("CLIENT_IP_HEADER", "x-forwarded-for")
    monkeypatch.setenv("CLIENT_IP_PROXY_HOPS", "2")
    assert client_key(FakeRequest()) == client_key(Direct())
