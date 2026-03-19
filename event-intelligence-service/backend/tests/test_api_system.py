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

    def test_404_when_no_data(self):
        #pipeline hasn't been run yet so there's nothing on disc
        with patch("app.routes.analysis_routes.load_standardised", return_value=None):
            response = client.get("/api/sentiment?stock=BHP")
            assert response.status_code == 404

    def test_missing_stock_param_returns_422(self):
        response = client.get("/api/sentiment")
        assert response.status_code == 422

    def test_unknown_stock_returns_neutral_sentiment(self):
        #xyz has no events in the dataset so should default to neutral
        with patch("app.routes.analysis_routes.load_standardised", return_value=MOCK_DATASET):
            response = client.get("/api/sentiment?stock=XYZ")
            assert response.status_code == 200
            assert response.json()["overall_sentiment"] == "neutral"


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

