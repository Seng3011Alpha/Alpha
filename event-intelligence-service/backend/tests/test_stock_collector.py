#tests for stock_collector - yahoo finance fetching, normalisation and mock fallback
import pytest
from unittest.mock import patch, MagicMock
from app.collectors.stock_collector import (
    fetch_stock_data,
    fetch_multiple_stocks,
    _normalize_symbol,
    _mock_stock_data,
    _fetch_yahoo_chart,
)


#realistic yahoo finance chart api response shape
YAHOO_RESPONSE = {
    "chart": {
        "result": [
            {
                "meta": {"shortName": "BHP Group", "symbol": "BHP.AX"},
                "timestamp": [1704067200, 1704153600],
                "indicators": {
                    "quote": [
                        {
                            "close": [44.80, 45.20],
                            "open": [44.50, 44.80],
                            "volume": [900000, 1000000],
                        }
                    ]
                },
            }
        ]
    }
}

YAHOO_EMPTY_RESULT = {"chart": {"result": None}}
YAHOO_NO_CLOSES = {
    "chart": {
        "result": [
            {
                "meta": {"shortName": "BHP Group"},
                "timestamp": [],
                "indicators": {"quote": [{"close": [], "open": [], "volume": []}]},
            }
        ]
    }
}


class TestFetchYahooChart:
    def test_returns_stock_data_on_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = YAHOO_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = _fetch_yahoo_chart("BHP.AX")
        assert result is not None
        assert result["ticker"] == "BHP.AX"
        assert result["Quote Price"] == 45.2
        assert result["data_source"] == "yahoo_finance"

    def test_returns_none_on_empty_result(self):
        #yahoo sometimes returns a null result block - should handle gracefully
        mock_resp = MagicMock()
        mock_resp.json.return_value = YAHOO_EMPTY_RESULT
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = _fetch_yahoo_chart("BHP.AX")
        assert result is None

    def test_returns_none_on_network_error(self):
        with patch("app.collectors.stock_collector.requests.get", side_effect=Exception("timeout")):
            result = _fetch_yahoo_chart("BHP.AX")
        assert result is None

    def test_returns_none_when_no_valid_closes(self):
        #all close values are none/empty so there's nothing to work with
        mock_resp = MagicMock()
        mock_resp.json.return_value = YAHOO_NO_CLOSES
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = _fetch_yahoo_chart("BHP.AX")
        assert result is None

    def test_single_close_uses_same_as_prev(self):
        #only one day of data so prev close equals latest - change should be zero
        single_close = {
            "chart": {
                "result": [
                    {
                        "meta": {"shortName": "BHP Group"},
                        "timestamp": [1704067200],
                        "indicators": {
                            "quote": [{"close": [45.0], "open": [44.5], "volume": [1000000]}]
                        },
                    }
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = single_close
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = _fetch_yahoo_chart("BHP.AX")
        assert result is not None
        assert result["change_percent"] == 0.0

    def test_required_keys_in_result(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = YAHOO_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = _fetch_yahoo_chart("BHP.AX")
        for key in ("ticker", "Quote Price", "Previous Close", "Open", "Volume", "change_percent", "timestamp", "company", "data_source"):
            assert key in result


class TestNormalizeSymbol:
    def test_adds_ax_suffix(self):
        assert _normalize_symbol("BHP") == "BHP.AX"

    def test_keeps_existing_suffix(self):
        assert _normalize_symbol("BHP.AX") == "BHP.AX"

    def test_lowercase_input(self):
        assert _normalize_symbol("cba") == "cba.AX"


class TestMockStockData:
    def test_known_ticker_returns_real_mock_price(self):
        result = _mock_stock_data("BHP.AX")
        assert result["ticker"] == "BHP.AX"
        assert result["Quote Price"] == 45.20
        assert result["data_source"] == "mock"

    def test_unknown_ticker_returns_default(self):
        #anything not in the hardcoded dict should get the default price
        result = _mock_stock_data("XYZ.AX")
        assert result["ticker"] == "XYZ.AX"
        assert result["Quote Price"] == 50.0

    def test_required_keys_present(self):
        result = _mock_stock_data("BHP.AX")
        for key in ("ticker", "Quote Price", "Previous Close", "Open", "Volume", "change_percent", "timestamp", "company", "data_source"):
            assert key in result

    def test_change_percent_calculation(self):
        result = _mock_stock_data("BHP.AX")
        expected = round((45.20 - 44.80) / 44.80 * 100, 2)
        assert result["change_percent"] == expected


class TestFetchStockData:
    def test_returns_data_from_yahoo(self):
        fake_data = {"ticker": "BHP.AX", "Quote Price": 45.0, "data_source": "yahoo_finance"}
        with patch("app.collectors.stock_collector._fetch_yahoo_chart", return_value=fake_data):
            result = fetch_stock_data("BHP")
            assert result == fake_data

    def test_falls_back_to_mock_when_yahoo_fails(self):
        with patch("app.collectors.stock_collector._fetch_yahoo_chart", return_value=None), \
             patch.dict("os.environ", {"USE_MOCK_STOCKS": "true"}):
            result = fetch_stock_data("BHP")
            assert result is not None
            assert result["data_source"] == "mock"

    def test_returns_none_when_yahoo_fails_and_mock_disabled(self):
        with patch("app.collectors.stock_collector._fetch_yahoo_chart", return_value=None), \
             patch.dict("os.environ", {"USE_MOCK_STOCKS": "false"}):
            result = fetch_stock_data("BHP")
            assert result is None


class TestFetchMultipleStocks:
    def test_returns_list_of_results(self):
        fake_data = {"ticker": "BHP.AX", "Quote Price": 45.0, "data_source": "yahoo_finance"}
        with patch("app.collectors.stock_collector._fetch_yahoo_chart", return_value=fake_data), \
             patch("app.collectors.stock_collector.time.sleep"):
            results = fetch_multiple_stocks(["BHP", "CBA"])
            assert len(results) == 2

    def test_uses_mock_for_failed_tickers(self):
        with patch("app.collectors.stock_collector._fetch_yahoo_chart", return_value=None), \
             patch.dict("os.environ", {"USE_MOCK_STOCKS": "true"}), \
             patch("app.collectors.stock_collector.time.sleep"):
            results = fetch_multiple_stocks(["BHP", "CBA"])
            assert all(r["data_source"] == "mock" for r in results)

    def test_empty_list_returns_empty(self):
        with patch("app.collectors.stock_collector.time.sleep"):
            results = fetch_multiple_stocks([])
            assert results == []

