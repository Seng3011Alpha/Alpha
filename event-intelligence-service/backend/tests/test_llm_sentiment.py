#tests for the llm-backed sentiment path and the written report service
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.services import analysis_service
from app.services import report_service


def _make_msg(text: str):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def test_sentiment_falls_back_without_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(analysis_service, "_CACHE_PATH", tmp_path / "cache.json")
    sentiment, score = analysis_service.analyse_sentiment_llm("BHP surges on record profit")
    assert sentiment == "positive"
    assert 0.5 < score <= 1.0


def test_sentiment_uses_llm_when_key_present(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(analysis_service, "_CACHE_PATH", tmp_path / "cache.json")

    class FakeClient:
        def __init__(self, *a, **kw):
            self.messages = self
        def create(self, **kw):
            return _make_msg('{"sentiment":"negative","score":0.82}')

    with patch("anthropic.Anthropic", FakeClient):
        sentiment, score = analysis_service.analyse_sentiment_llm("Mining sector faces headwinds")
    assert sentiment == "negative"
    assert score == 0.82


def test_sentiment_parses_json_embedded_in_prose(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(analysis_service, "_CACHE_PATH", tmp_path / "cache.json")

    class FakeClient:
        def __init__(self, *a, **kw):
            self.messages = self
        def create(self, **kw):
            return _make_msg('Here is the result: {"sentiment":"positive","score":0.7} thanks')

    with patch("anthropic.Anthropic", FakeClient):
        sentiment, score = analysis_service.analyse_sentiment_llm("Strong quarter")
    assert sentiment == "positive"
    assert score == 0.7


def test_sentiment_falls_back_on_garbage_response(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(analysis_service, "_CACHE_PATH", tmp_path / "cache.json")

    class FakeClient:
        def __init__(self, *a, **kw):
            self.messages = self
        def create(self, **kw):
            return _make_msg("i cannot help with that")

    with patch("anthropic.Anthropic", FakeClient):
        sentiment, score = analysis_service.analyse_sentiment_llm("profit beat expectations")
    #sentiment should still land on positive via fallback keyword path
    assert sentiment in {"positive", "neutral"}
    assert 0.0 <= score <= 1.0


def test_sentiment_caches_results(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    cache = tmp_path / "cache.json"
    monkeypatch.setattr(analysis_service, "_CACHE_PATH", cache)

    calls = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **kw):
            self.messages = self
        def create(self, **kw):
            calls["n"] += 1
            return _make_msg('{"sentiment":"neutral","score":0.5}')

    with patch("anthropic.Anthropic", FakeClient):
        analysis_service.analyse_sentiment_llm("market was flat today")
        analysis_service.analyse_sentiment_llm("market was flat today")
    assert calls["n"] == 1
    assert cache.exists()


def test_empty_text_returns_neutral_zero(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    sentiment, score = analysis_service.analyse_sentiment_llm("")
    assert sentiment == "neutral"
    assert score == 0.0


def test_report_fallback_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(report_service, "_REPORTS_DIR", tmp_path)

    result = report_service.generate_stock_report(
        ticker="BHP.AX",
        quote={"company": "BHP Group", "Quote Price": 45.2, "change_percent": 0.89},
        news=[
            {"title": "BHP profit beats", "source": "AFR", "sentiment": "positive", "impact_score": 0.8},
            {"title": "Mining headwinds", "source": "SMH", "sentiment": "negative", "impact_score": 0.6},
        ],
        indicators={"MA5": 45.0, "MA20": 44.8},
    )
    assert result["stock"] == "BHP.AX"
    assert result["model"] == "fallback"
    assert result["articles_considered"] == 2
    assert result["overall_sentiment"] in {"positive", "negative", "neutral"}
    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 0


def test_report_uses_llm_when_key_present(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(report_service, "_REPORTS_DIR", tmp_path)

    body = {
        "summary": "BHP looks solid.\n\nIron ore demand is strong.",
        "key_drivers": ["Iron ore demand", "Record profit"],
        "risks": ["China slowdown"],
        "overall_sentiment": "positive",
    }

    class FakeClient:
        def __init__(self, *a, **kw):
            self.messages = self
        def create(self, **kw):
            return _make_msg(json.dumps(body))

    with patch("anthropic.Anthropic", FakeClient):
        result = report_service.generate_stock_report(
            ticker="BHP",
            quote={"Quote Price": 45.2, "change_percent": 0.89},
            news=[{"title": "BHP up", "sentiment": "positive", "impact_score": 0.7}],
            indicators=None,
            force_refresh=True,
        )
    assert result["overall_sentiment"] == "positive"
    assert "Iron ore demand" in result["key_drivers"]
    assert result["model"].startswith("claude")
