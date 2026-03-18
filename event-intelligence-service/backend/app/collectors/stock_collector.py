import os
import time
from datetime import datetime
from typing import Optional

import requests

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_CHART_URL_FALLBACK = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"

REQUEST_TIMEOUT = 10
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-AU,en;q=0.9",
    "Origin": "https://finance.yahoo.com",
    "Referer": "https://finance.yahoo.com/",
}

MOCK_PRICES: dict[str, tuple[float, float]] = {
    "BHP.AX": (45.20, 44.80),
    "CBA.AX": (128.50, 127.90),
    "NAB.AX": (35.60, 35.40),
    "WBC.AX": (27.30, 27.10),
    "ANZ.AX": (29.80, 29.50),
    "RIO.AX": (118.00, 116.50),
    "WDS.AX": (24.10, 23.80),
    "MQG.AX": (198.00, 195.00),
    "CSL.AX": (285.00, 282.00),
    "WOW.AX": (32.40, 32.00),
}


def _normalise_symbol(ticker: str) -> str:
    return ticker if ticker.endswith(".AX") else f"{ticker}.AX"


def _fetch_yahoo_chart(symbol: str) -> Optional[dict]:
    #fetch ohlcv data from yahoo finance v8 api; tries query1 first then query2 as fallback
    params = {"range": "5d", "interval": "1d", "includePrePost": "false"}

    for base_url in (YAHOO_CHART_URL, YAHOO_CHART_URL_FALLBACK):
        try:
            url = base_url.format(symbol=symbol)
            resp = requests.get(url, headers=REQUEST_HEADERS, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            result = data.get("chart", {}).get("result")
            if not result:
                continue

            chart = result[0]
            meta = chart.get("meta", {})
            timestamps = chart.get("timestamp", [])
            indicators = chart.get("indicators", {}).get("quote", [{}])[0]

            closes = indicators.get("close", [])
            opens = indicators.get("open", [])
            volumes = indicators.get("volume", [])

            valid_closes = [c for c in closes if c is not None]
            if len(valid_closes) < 1:
                continue

            latest_close = valid_closes[-1]
            prev_close = valid_closes[-2] if len(valid_closes) > 1 else valid_closes[0]
            latest_open = next((o for o in reversed(opens) if o is not None), prev_close)
            latest_vol = next((v for v in reversed(volumes) if v is not None), 0)

            #prefer meta fields - more reliable than reconstructing from the close array
            quote_price = meta.get("regularMarketPrice") or latest_close
            prev_close_val = meta.get("previousClose") or prev_close
            change_pct = meta.get("regularMarketChangePercent") or (
                ((quote_price - prev_close_val) / prev_close_val * 100) if prev_close_val else 0
            )

            return {
                "ticker": symbol,
                "Quote Price": round(float(quote_price), 3),
                "Previous Close": round(float(prev_close_val), 3),
                "Open": round(float(latest_open), 3),
                "Volume": int(latest_vol),
                "change_percent": round(change_pct, 2),
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "company": meta.get("shortName") or meta.get("symbol", symbol),
                "data_source": "yahoo_finance",
            }
        except Exception:
            continue

    return None


def _mock_stock_data(symbol: str) -> dict:
    #fallback when all real data sources fail
    price, prev = MOCK_PRICES.get(symbol, (50.0, 49.5))
    return {
        "ticker": symbol,
        "Quote Price": price,
        "Previous Close": prev,
        "Open": prev,
        "Volume": 1000000,
        "change_percent": round((price - prev) / prev * 100, 2),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "company": symbol,
        "data_source": "mock",
    }


def fetch_stock_data(ticker: str) -> Optional[dict]:
    #fetch a single asx stock; returns none if fetch fails and mock is disabled
    symbol = _normalise_symbol(ticker)
    result = _fetch_yahoo_chart(symbol)
    if result:
        return result

    if os.getenv("USE_MOCK_STOCKS", "true").lower() == "true":
        return _mock_stock_data(symbol)
    return None


def fetch_multiple_stocks(tickers: list[str]) -> list[dict]:
    #fetch multiple asx stocks in sequence with a short delay to reduce rate limiting
    symbols = [_normalise_symbol(t) for t in tickers]
    results = []

    for sym in symbols:
        data = _fetch_yahoo_chart(sym)
        if data:
            results.append(data)
        else:
            if os.getenv("USE_MOCK_STOCKS", "true").lower() == "true":
                results.append(_mock_stock_data(sym))
        time.sleep(0.5)

    return results
