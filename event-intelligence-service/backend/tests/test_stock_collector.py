#tests for stock_collector - yahoo finance fetching, normalisation and mock fallback
import pytest
from unittest.mock import patch, MagicMock
from app.collectors.stock_collector import (
    fetch_stock_data,
    fetch_multiple_stocks,
    fetch_stock_history,
    _normalise_symbol,
    _mock_stock_data,
    _fetch_yahoo_chart,
    _compute_indicators,
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
        assert _normalise_symbol("BHP") == "BHP.AX"

    def test_keeps_existing_suffix(self):
        assert _normalise_symbol("BHP.AX") == "BHP.AX"

    def test_lowercase_input(self):
        #lowercase should be uppercased so stored tickers always match query lookups
        assert _normalise_symbol("cba") == "CBA.AX"


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

YAHOO_HISTORY_RESPONSE = {
    "chart": {
        "result": [
            {
                "meta": {
                    "shortName": "BHP Group",
                    "symbol": "BHP.AX",
                    "regularMarketPrice": 45.20,
                    "previousClose": 44.80,
                    "regularMarketChangePercent": 0.89,
                    "fiftyTwoWeekHigh": 50.0,
                    "fiftyTwoWeekLow": 40.0,
                    "regularMarketDayHigh": 45.5,
                    "regularMarketDayLow": 44.0,
                },
                "timestamp": [1704067200, 1704153600],
                "indicators": {
                    "quote": [
                        {
                            "open": [44.50, 44.80],
                            "high": [45.0, 45.5],
                            "low": [44.0, 44.3],
                            "close": [44.80, 45.20],
                            "volume": [900000, 1000000],
                        }
                    ],
                    "adjclose": [{"adjclose": [44.80, 45.20]}],
                },
            }
        ]
    }
}


class TestFetchStockHistory:
    def _make_mock_resp(self, payload):
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_returns_full_result_dict(self):
        mock_resp = self._make_mock_resp(YAHOO_HISTORY_RESPONSE)
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = fetch_stock_history("BHP")
        assert result is not None
        for key in ("quote", "ohlc_series", "indicators", "period"):
            assert key in result

    def test_quote_has_correct_ticker(self):
        mock_resp = self._make_mock_resp(YAHOO_HISTORY_RESPONSE)
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = fetch_stock_history("BHP")
        assert result["quote"]["ticker"] == "BHP.AX"
        assert result["quote"]["data_source"] == "yahoo_finance"

    def test_ohlc_series_has_expected_keys(self):
        mock_resp = self._make_mock_resp(YAHOO_HISTORY_RESPONSE)
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = fetch_stock_history("BHP")
        assert len(result["ohlc_series"]) == 2
        for row in result["ohlc_series"]:
            for key in ("date", "Open", "High", "Low", "Close", "Adj Close", "Volume"):
                assert key in row

    def test_indicators_keys_present(self):
        mock_resp = self._make_mock_resp(YAHOO_HISTORY_RESPONSE)
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = fetch_stock_history("BHP")
        ind = result["indicators"]
        for key in ("MA5", "MA20", "volatility_annual_pct", "week52_high", "week52_low", "days_high", "days_low"):
            assert key in ind

    def test_period_is_passed_through(self):
        mock_resp = self._make_mock_resp(YAHOO_HISTORY_RESPONSE)
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = fetch_stock_history("BHP", period="3mo")
        assert result["period"] == "3mo"

    def test_returns_none_on_empty_chart_result(self):
        mock_resp = self._make_mock_resp({"chart": {"result": None}})
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = fetch_stock_history("BHP")
        assert result is None

    def test_returns_none_on_network_error(self):
        with patch("app.collectors.stock_collector.requests.get", side_effect=Exception("timeout")):
            result = fetch_stock_history("BHP")
        assert result is None

    def test_skips_rows_with_none_close(self):
        payload_with_none = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "shortName": "BHP Group",
                            "regularMarketPrice": 45.20,
                            "previousClose": 44.80,
                        },
                        "timestamp": [1704067200, 1704153600, 1704240000],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [44.50, None, 44.80],
                                    "high": [45.0, None, 45.5],
                                    "low": [44.0, None, 44.3],
                                    "close": [44.80, None, 45.20],
                                    "volume": [900000, None, 1000000],
                                }
                            ],
                            "adjclose": [{"adjclose": [44.80, None, 45.20]}],
                        },
                    }
                ]
            }
        }
        mock_resp = self._make_mock_resp(payload_with_none)
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp):
            result = fetch_stock_history("BHP")
        assert result is not None
        assert len(result["ohlc_series"]) == 2

    def test_normalises_ticker_before_request(self):
        mock_resp = self._make_mock_resp(YAHOO_HISTORY_RESPONSE)
        with patch("app.collectors.stock_collector.requests.get", return_value=mock_resp) as mock_get:
            fetch_stock_history("bhp")
        called_url = mock_get.call_args[0][0]
        assert "BHP.AX" in called_url


class TestComputeIndicators:
    def test_ma5_correct_for_five_values(self):
        closes = [10.0, 11.0, 12.0, 13.0, 14.0]
        result = _compute_indicators(closes, {})
        assert result["MA5"] == round(sum(closes) / 5, 3)

    def test_ma5_uses_all_values_when_fewer_than_five(self):
        closes = [10.0, 12.0]
        result = _compute_indicators(closes, {})
        assert result["MA5"] == round(sum(closes) / 2, 3)

    def test_ma20_uses_available_when_fewer_than_twenty(self):
        closes = [float(i) for i in range(1, 6)]
        result = _compute_indicators(closes, {})
        assert result["MA20"] == round(sum(closes) / 5, 3)

    def test_volatility_is_none_for_single_close(self):
        result = _compute_indicators([45.0], {})
        assert result["volatility_annual_pct"] is None

    def test_volatility_is_float_for_multiple_closes(self):
        closes = [44.80, 45.20, 44.50, 45.00, 45.30]
        result = _compute_indicators(closes, {})
        assert isinstance(result["volatility_annual_pct"], float)
        assert result["volatility_annual_pct"] >= 0

    def test_week52_sourced_from_meta(self):
        meta = {"fiftyTwoWeekHigh": 55.0, "fiftyTwoWeekLow": 38.0}
        result = _compute_indicators([45.0, 46.0], meta)
        assert result["week52_high"] == 55.0
        assert result["week52_low"] == 38.0

    def test_days_range_sourced_from_meta(self):
        meta = {"regularMarketDayHigh": 46.0, "regularMarketDayLow": 44.5}
        result = _compute_indicators([45.0, 46.0], meta)
        assert result["days_high"] == 46.0
        assert result["days_low"] == 44.5

    def test_missing_meta_keys_return_none(self):
        result = _compute_indicators([45.0, 46.0], {})
        assert result["week52_high"] is None
        assert result["week52_low"] is None
        assert result["days_high"] is None
        assert result["days_low"] is None

