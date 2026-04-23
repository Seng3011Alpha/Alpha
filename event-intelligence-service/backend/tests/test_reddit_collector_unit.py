from datetime import datetime, timezone

import pytest

from app.collectors import reddit_collector as rc


class _DummyResponse:
    def __init__(self, payload, status_ok=True):
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


def test_extract_events_supports_top_level_and_nested():
    top_payload = {"events": [{"id": 1}]}
    nested_payload = {"data": {"events": [{"id": 2}]}}
    empty_payload = {"data": {"other": []}}

    assert rc._extract_events(top_payload) == [{"id": 1}]
    assert rc._extract_events(nested_payload) == [{"id": 2}]
    assert rc._extract_events(empty_payload) == []


def test_to_iso_utc_handles_timestamp_iso_and_invalid():
    from_timestamp = rc._to_iso_utc(0)
    from_iso = rc._to_iso_utc("2024-01-01T00:00:00Z")
    from_invalid = rc._to_iso_utc("not-a-date")

    assert from_timestamp.startswith("1970-01-01T00:00:00")
    assert from_iso.startswith("2024-01-01T00:00:00")
    assert datetime.fromisoformat(from_invalid).tzinfo == timezone.utc


def test_fetch_reddit_posts_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setenv("USE_EXTERNAL_REDDIT_API", "false")
    assert rc.fetch_reddit_posts() == []


def test_fetch_reddit_posts_returns_empty_without_credentials(monkeypatch):
    monkeypatch.setenv("USE_EXTERNAL_REDDIT_API", "true")
    monkeypatch.delenv("EXTERNAL_API_TEST_EMAIL", raising=False)
    monkeypatch.delenv("EXTERNAL_API_TEST_PASSWORD", raising=False)
    assert rc.fetch_reddit_posts() == []


def test_fetch_reddit_posts_normalises_payload_and_uses_fallback(monkeypatch):
    monkeypatch.setenv("USE_EXTERNAL_REDDIT_API", "true")
    monkeypatch.setenv("EXTERNAL_API_BASE_URL", "https://unit.test")
    monkeypatch.setenv("EXTERNAL_API_TEST_EMAIL", "test@example.com")
    monkeypatch.setenv("EXTERNAL_API_TEST_PASSWORD", "secret")
    monkeypatch.setenv("EXTERNAL_API_ASX_LIMIT", "5")

    calls = {"get": 0}

    def fake_post(url, json, timeout):
        assert url == "https://unit.test/v1/auth/login"
        assert json["email"] == "test@example.com"
        assert timeout == rc.REQUEST_TIMEOUT
        return _DummyResponse({"token": "abc-token"})

    def fake_get(url, params, headers, timeout):
        calls["get"] += 1
        assert url == "https://unit.test/v1/post/search"
        assert headers == {"Authorization": "Bearer abc-token"}
        assert timeout == rc.REQUEST_TIMEOUT
        if calls["get"] == 1:
            assert "after" in params
            return _DummyResponse({"events": []})
        return _DummyResponse(
            {
                "data": {
                    "events": [
                        {"attributes": "bad-attrs"},
                        {"attributes": {"title": "", "selftext": ""}},
                        {
                            "attributes": {
                                "id": "p1",
                                "title": "ASX rally",
                                "selftext": "BHP is up",
                                "author": "u1",
                                "subreddit": "ASX_Bets",
                                "score": 12,
                                "created_utc": 1704067200,
                            }
                        },
                    ]
                }
            }
        )

    monkeypatch.setattr(rc.requests, "post", fake_post)
    monkeypatch.setattr(rc.requests, "get", fake_get)

    posts = rc.fetch_reddit_posts(query="ASX", subreddit="ASX_Bets", limit=3)
    assert len(posts) == 1
    assert posts[0]["id"] == "p1"
    assert posts[0]["title"] == "ASX rally"
    assert posts[0]["body"] == "BHP is up"
    assert posts[0]["data_source"] == "reddit_external_api"
    assert calls["get"] == 2


def test_fetch_reddit_posts_handles_http_errors(monkeypatch):
    monkeypatch.setenv("USE_EXTERNAL_REDDIT_API", "true")
    monkeypatch.setenv("EXTERNAL_API_BASE_URL", "https://unit.test")
    monkeypatch.setenv("EXTERNAL_API_TEST_EMAIL", "test@example.com")
    monkeypatch.setenv("EXTERNAL_API_TEST_PASSWORD", "secret")

    def fake_post(url, json, timeout):
        return _DummyResponse({"token": "abc-token"})

    def fake_get(url, params, headers, timeout):
        raise RuntimeError("network down")

    monkeypatch.setattr(rc.requests, "post", fake_post)
    monkeypatch.setattr(rc.requests, "get", fake_get)

    assert rc.fetch_reddit_posts() == []


def test_login_token_accepts_access_token(monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_TEST_EMAIL", "test@example.com")
    monkeypatch.setenv("EXTERNAL_API_TEST_PASSWORD", "secret")

    def fake_post(url, json, timeout):
        return _DummyResponse({"access_token": "xyz"})

    monkeypatch.setattr(rc.requests, "post", fake_post)
    assert rc._login_token("https://unit.test") == "xyz"

