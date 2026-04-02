#system tests - full http request/response cycle for all api endpoints
#external services (yahoo finance, google news) are mocked throughout
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


MOCK_STOCK = {
    "ticker": "BHP.AX",
    "Quote Price": 45.20,
    "Previous Close": 44.80,
    "Open": 44.80,
    "Volume": 1000000,
    "change_percent": 0.89,
    "timestamp": "2024-01-01 00:00:00",
    "company": "BHP Group",
    "data_source": "yahoo_finance",
}

MOCK_NEWS = [
    {
        "title": "BHP surges on strong iron ore demand",
        "source": "AFR",
        "url": "https://example.com/bhp",
        "published_at": "2024-01-01T00:00:00+00:00",
        "description": "BHP reported strong gains today.",
    }
]

#pre-built standardised dataset matching the adage 3.0 schema
MOCK_DATASET = {
    "data_source": "event_intelligence",
    "dataset_type": "Mixed",
    "dataset_id": "s3://event-intelligence/combined_events.json",
    "time_object": {"timestamp": "2024-01-01 00:00:00", "timezone": "UTC"},
    "events": [
        {
            "time_object": {"timestamp": "2024-01-01 00:00:00", "timezone": "UTC"},
            "event_type": "Stock quote",
            "attribute": {
                "ticker": "BHP.AX",
                "Quote Price": 45.20,
                "Previous Close": 44.80,
                "Open": 44.80,
                "Volume": 1000000,
                "change_percent": 0.89,
                "data_source": "Yahoo finance",
            },
        },
        {
            "time_object": {"timestamp": "2024-01-01 00:00:00", "duration": 1, "duration_unit": "hour", "timezone": "UTC"},
            "event_type": "Stock news",
            "attribute": {
                "title": "BHP surges on strong iron ore demand",
                "summary": "BHP surges on strong iron ore demand BHP reported strong gains today.",
                "link": "https://example.com/bhp",
                "published": "2024-01-01T00:00:00+00:00",
                "source": "AFR",
                "region": "AU",
                "sentiment": "positive",
                "impact_score": 0.65,
                "related_stock": "BHP.AX",
                "data_source": "yahoo_finance",
            },
        },
    ],
}

MOCK_HISTORY_RESULT = {
    "quote": MOCK_STOCK,
    "ohlc_series": [
        {
            "date": "2024-01-01",
            "Open": 44.5, "High": 45.5, "Low": 44.0,
            "Close": 45.0, "Adj Close": 45.0, "Volume": 1000000,
        }
    ],
    "indicators": {
        "MA5": 45.0, "MA20": 44.8,
        "volatility_annual_pct": 15.2,
        "week52_high": 50.0, "week52_low": 40.0,
        "days_high": 45.5, "days_low": 44.0,
    },
    "period": "1mo",
}

MOCK_HISTORY_DATASET = {
    "data_source": "event_intelligence",
    "dataset_type": "Daily stock data",
    "dataset_id": "s3://event-intelligence/history_events.json",
    "time_object": {"timestamp": "2024-01-01 00:00:00", "timezone": "UTC"},
    "events": [
        {
            "time_object": {"timestamp": "2024-01-01", "timezone": "UTC"},
            "event_type": "Stock ohlc",
            "attribute": {
                "ticker": "BHP.AX",
                "Open": 44.5, "High": 45.5, "Low": 44.0,
                "Close": 45.0, "Adj Close": 45.0, "Volume": 1000000,
                "date": "2024-01-01",
                "data_source": "yahoo_finance",
            },
        },
        {
            "time_object": {"timestamp": "2024-01-01 00:00:00", "timezone": "UTC"},
            "event_type": "Stock analysis",
            "attribute": {
                "ticker": "BHP.AX",
                "MA5": 45.0, "MA20": 44.8,
                "volatility_annual_pct": 15.2,
                "week52_high": 50.0, "week52_low": 40.0,
                "days_high": 45.5, "days_low": 44.0,
                "period": "1mo",
                "data_source": "yahoo_finance",
            },
        },
    ],
}

class TestRoot:
    def test_root_returns_200(self):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_message(self):
        response = client.get("/")
        assert "message" in response.json()


class TestCollectStocks:
    def test_collect_stocks_success(self, tmp_path):
        with patch("app.routes.collect_routes.fetch_multiple_stocks", return_value=[MOCK_STOCK]), \
             patch("app.routes.collect_routes.save_raw"):
            response = client.post("/collect/stocks")
            assert response.status_code == 200
            body = response.json()
            assert body["collected"] == 1
            assert "BHP.AX" in body["tickers"]

    def test_collect_stocks_custom_tickers(self):
        #check the tickers from the query string actually get passed down
        with patch("app.routes.collect_routes.fetch_multiple_stocks", return_value=[MOCK_STOCK]) as mock_fetch, \
             patch("app.routes.collect_routes.save_raw"):
            response = client.post("/collect/stocks?tickers=BHP,CBA")
            assert response.status_code == 200
            called_with = mock_fetch.call_args[0][0]
            assert "BHP" in called_with
            assert "CBA" in called_with

    def test_collect_stocks_503_when_no_data(self):
        #empty list from collector means all fetches failed
        with patch("app.routes.collect_routes.fetch_multiple_stocks", return_value=[]):
            response = client.post("/collect/stocks")
            assert response.status_code == 503


class TestCollectNews:
    def test_collect_news_success(self):
        with patch("app.routes.collect_routes.fetch_financial_news", return_value=MOCK_NEWS), \
             patch("app.routes.collect_routes.save_raw"):
            response = client.post("/collect/news")
            assert response.status_code == 200
            assert response.json()["collected"] == 1

    def test_collect_news_returns_count(self):
        with patch("app.routes.collect_routes.fetch_financial_news", return_value=MOCK_NEWS * 3), \
             patch("app.routes.collect_routes.save_raw"):
            response = client.post("/collect/news")
            assert response.json()["collected"] == 3


class TestCollectPipeline:
    def test_pipeline_success(self):
        with patch("app.routes.collect_routes.fetch_multiple_stocks", return_value=[MOCK_STOCK]), \
             patch("app.routes.collect_routes.fetch_financial_news", return_value=MOCK_NEWS), \
             patch("app.routes.collect_routes.save_standardised"):
            response = client.post("/collect/pipeline")
            assert response.status_code == 200
            body = response.json()
            assert body["stocks"] == 1
            assert body["news"] == 1
            assert body["events_count"] == 2  #one stock event + one news event

    def test_pipeline_custom_tickers(self):
        with patch("app.routes.collect_routes.fetch_multiple_stocks", return_value=[MOCK_STOCK]) as mock_fetch, \
             patch("app.routes.collect_routes.fetch_financial_news", return_value=[]), \
             patch("app.routes.collect_routes.save_standardised"):
            client.post("/collect/pipeline?tickers=RIO,WDS")
            called_with = mock_fetch.call_args[0][0]
            assert "RIO" in called_with
            assert "WDS" in called_with


class TestGetSentiment:
    def test_returns_sentiment_for_stock(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            response = client.get("/api/sentiment?stock=BHP")
            assert response.status_code == 200
            body = response.json()
            assert body["stock"] == "BHP.AX"
            assert body["stock_data"] is not None
            assert "overall_sentiment" in body

    def test_ax_suffix_normalisation(self):
        #bhp and bhp.ax should resolve to the same ticker
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            r1 = client.get("/api/sentiment?stock=BHP")
            r2 = client.get("/api/sentiment?stock=BHP.AX")
            assert r1.json()["stock"] == r2.json()["stock"]

    def test_live_fetch_when_no_cache(self):
        #no cache on disc falls back to live fetch and still returns 200
        with patch("app.routes.analysis_routes.load_standardised", return_value=None), \
             patch("app.routes.analysis_routes.fetch_stock_data", return_value=MOCK_STOCK), \
             patch("app.routes.analysis_routes.fetch_financial_news", return_value=MOCK_NEWS):
            response = client.get("/api/sentiment?stock=BHP")
            assert response.status_code == 200
            body = response.json()
            assert body["cached"] is False
            assert body["stock_data"] is not None
            assert "overall_sentiment" in body

    def test_missing_stock_param_returns_422(self):
        response = client.get("/api/sentiment")
        assert response.status_code == 422

    def test_unknown_stock_returns_neutral_sentiment(self):
        #xyz has no events in the dataset so should default to neutral
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            response = client.get("/api/sentiment?stock=XYZ")
            assert response.status_code == 200
            assert response.json()["overall_sentiment"] == "neutral"



class TestGetNews:
    def test_returns_news_from_cache(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            response = client.get("/api/news")
            assert response.status_code == 200
            body = response.json()
            assert body["cached"] is True
            assert len(body["events"]) >= 1
            assert all(e["event_type"] == "Stock news" for e in body["events"])

    def test_ticker_filter_returns_matching_events(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            response = client.get("/api/news?ticker=BHP")
            assert response.status_code == 200
            events = response.json()["events"]
            for e in events:
                related = e["attribute"].get("related_stock")
                assert related == "BHP.AX" or related is None

    def test_limit_is_respected(self):
        big_dataset = {**MOCK_DATASET, "events": MOCK_DATASET["events"] * 10}
        with patch("app.routes.analysis_routes.load_standardised", return_value=big_dataset):
            response = client.get("/api/news?limit=3")
            assert response.status_code == 200
            assert len(response.json()["events"]) <= 3

    def test_live_fetch_when_no_cache(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=None), \
             patch("app.routes.analysis_routes.fetch_financial_news", return_value=MOCK_NEWS):
            response = client.get("/api/news")
            assert response.status_code == 200
            body = response.json()
            assert body["cached"] is False
            assert len(body["events"]) == 1

    def test_live_fetch_with_ticker_filter(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=None), \
             patch("app.routes.analysis_routes.fetch_financial_news", return_value=MOCK_NEWS):
            response = client.get("/api/news?ticker=BHP")
            assert response.status_code == 200

    def test_response_has_adage_fields(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            body = client.get("/api/news").json()
            for field in ("data_source", "dataset_type", "dataset_id", "time_object", "events"):
                assert field in body


class TestGetStock:
    def test_returns_stock_from_cache(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            response = client.get("/api/stock?ticker=BHP")
            assert response.status_code == 200
            body = response.json()
            assert body["cached"] is True
            assert any(e["event_type"] == "Stock quote" for e in body["events"])

    def test_ax_suffix_normalisation(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            r1 = client.get("/api/stock?ticker=BHP")
            r2 = client.get("/api/stock?ticker=BHP.AX")
            assert r1.status_code == r2.status_code == 200

    def test_live_fetch_when_no_cache(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=None), \
             patch("app.routes.analysis_routes.fetch_stock_data", return_value=MOCK_STOCK):
            response = client.get("/api/stock?ticker=BHP")
            assert response.status_code == 200
            body = response.json()
            assert body["cached"] is False

    def test_503_when_yahoo_fails_and_no_cache(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=None), \
             patch("app.routes.analysis_routes.fetch_stock_data", return_value=None):
            response = client.get("/api/stock?ticker=BHP")
            assert response.status_code == 503

    def test_missing_ticker_returns_422(self):
        response = client.get("/api/stock")
        assert response.status_code == 422

    def test_include_ohlc_appends_history_from_cache(self):
        with patch("app.routes.analysis_routes.load_standardised",
                   side_effect=[MOCK_DATASET, MOCK_HISTORY_DATASET]):
            response = client.get("/api/stock?ticker=BHP&include_ohlc=true")
            assert response.status_code == 200
            body = response.json()
            types = [e["event_type"] for e in body["events"]]
            assert "Stock ohlc" in types
            assert "Stock analysis" in types
            assert "ohlc_data_points" in body

    def test_include_ohlc_live_when_no_history_cache(self):
        with patch("app.routes.analysis_routes.load_standardised",
                   side_effect=[MOCK_DATASET, None]), \
             patch("app.routes.analysis_routes.fetch_stock_history",
                   return_value=MOCK_HISTORY_RESULT):
            response = client.get("/api/stock?ticker=BHP&include_ohlc=true")
            assert response.status_code == 200
            body = response.json()
            assert "ohlc_data_points" in body
            assert body["ohlc_data_points"] == 1


class TestGetAnalysis:
    def test_returns_analysis_from_history_cache(self):
        with patch("app.routes.analysis_routes.load_standardised",
                   return_value=MOCK_HISTORY_DATASET):
            response = client.get("/api/analysis?stock=BHP")
            assert response.status_code == 200
            body = response.json()
            assert body["cached"] is True
            assert body["stock"] == "BHP.AX"
            assert "indicators" in body
            assert "ohlc_series" in body

    def test_returns_ohlc_series_list(self):
        with patch("app.routes.analysis_routes.load_standardised",
                   return_value=MOCK_HISTORY_DATASET):
            body = client.get("/api/analysis?stock=BHP").json()
            assert isinstance(body["ohlc_series"], list)
            assert body["data_points"] == 1

    def test_live_fetch_when_no_cache(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=None), \
             patch("app.routes.analysis_routes.fetch_stock_history",
                   return_value=MOCK_HISTORY_RESULT):
            response = client.get("/api/analysis?stock=BHP")
            assert response.status_code == 200
            body = response.json()
            assert body["cached"] is False
            assert body["period"] == "1mo"

    def test_503_when_yahoo_fails_and_no_cache(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=None), \
             patch("app.routes.analysis_routes.fetch_stock_history", return_value=None):
            response = client.get("/api/analysis?stock=BHP")
            assert response.status_code == 503

    def test_missing_stock_param_returns_422(self):
        response = client.get("/api/analysis")
        assert response.status_code == 422

    def test_period_param_passed_to_live_fetch(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=None), \
             patch("app.routes.analysis_routes.fetch_stock_history",
                   return_value={**MOCK_HISTORY_RESULT, "period": "3mo"}) as mock_hist:
            response = client.get("/api/analysis?stock=BHP&period=3mo")
            assert response.status_code == 200
            mock_hist.assert_called_once_with("BHP.AX", period="3mo")


class TestCollectHistory:
    def test_history_success(self):
        with patch("app.routes.collect_routes.fetch_stock_history",
                   return_value=MOCK_HISTORY_RESULT), \
             patch("app.routes.collect_routes.save_raw"), \
             patch("app.routes.collect_routes.save_standardised"):
            response = client.post("/collect/history?tickers=BHP&period=1mo")
            assert response.status_code == 200
            body = response.json()
            assert "BHP" in body["tickers"]
            assert body["ohlc_events"] == 1
            assert body["analysis_events"] == 1

    def test_invalid_period_returns_400(self):
        response = client.post("/collect/history?period=2y")
        assert response.status_code == 400

    def test_valid_periods_accepted(self):
        for period in ("1mo", "3mo", "6mo", "1y"):
            with patch("app.routes.collect_routes.fetch_stock_history",
                       return_value=MOCK_HISTORY_RESULT), \
                 patch("app.routes.collect_routes.save_raw"), \
                 patch("app.routes.collect_routes.save_standardised"):
                response = client.post(f"/collect/history?tickers=BHP&period={period}")
                assert response.status_code == 200, f"Expected 200 for period={period}"

    def test_skips_tickers_with_failed_fetch(self):
        with patch("app.routes.collect_routes.fetch_stock_history", return_value=None), \
             patch("app.routes.collect_routes.save_raw"), \
             patch("app.routes.collect_routes.save_standardised"):
            response = client.post("/collect/history?tickers=BHP,CBA")
            assert response.status_code == 200
            assert response.json()["tickers"] == []

    def test_custom_tickers_passed_to_collector(self):
        with patch("app.routes.collect_routes.fetch_stock_history",
                   return_value=MOCK_HISTORY_RESULT) as mock_hist, \
             patch("app.routes.collect_routes.save_raw"), \
             patch("app.routes.collect_routes.save_standardised"):
            client.post("/collect/history?tickers=RIO,WDS&period=3mo")
            called_tickers = [call[0][0] for call in mock_hist.call_args_list]
            assert "RIO" in called_tickers
            assert "WDS" in called_tickers

    def test_default_tickers_used_when_none_given(self):
        with patch("app.routes.collect_routes.fetch_stock_history",
                   return_value=MOCK_HISTORY_RESULT) as mock_hist, \
             patch("app.routes.collect_routes.save_raw"), \
             patch("app.routes.collect_routes.save_standardised"):
            client.post("/collect/history")
            assert mock_hist.call_count == 5


class TestGetEvents:
    def test_returns_full_dataset(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            response = client.get("/api/events")
            assert response.status_code == 200
            body = response.json()
            assert "events" in body
            assert len(body["events"]) == 2

    def test_404_when_no_data(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=None):
            response = client.get("/api/events")
            assert response.status_code == 404

    def test_response_has_adage_fields(self):
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            body = client.get("/api/events").json()
            assert "data_source" in body
            assert "dataset_type" in body
            assert "time_object" in body

