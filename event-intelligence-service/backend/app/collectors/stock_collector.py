import os
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf


def _mock_stock_data(symbol: str) -> dict:
    """Fallback when Yahoo Finance is blocked or returns errors."""
    prices = {
        "BHP.AX": (45.20, 44.80),
        "CBA.AX": (128.50, 127.90),
        "NAB.AX": (35.60, 35.40),
        "WBC.AX": (27.30, 27.10),
        "ANZ.AX": (29.80, 29.50),
    }
    price, prev = prices.get(symbol, (50.0, 49.5))
    return {
        "ticker": symbol,
        "Quote Price": price,
        "Previous Close": prev,
        "Open": prev,
        "Volume": 1000000,
        "change_percent": round((price - prev) / prev * 100, 2),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "company": symbol,
    }


def _parse_ticker_from_download(df: pd.DataFrame, symbol: str) -> Optional[dict]:
    """Extract stock data from a DataFrame with Open/High/Low/Close/Volume columns."""
    try:
        latest = df["Close"].iloc[-1]
        prev = df["Close"].iloc[-2] if len(df) > 1 else latest
        change_pct = ((latest - prev) / prev * 100) if prev and prev != 0 else 0

        return {
            "ticker": symbol,
            "Quote Price": float(latest),
            "Previous Close": float(prev),
            "Open": float(df["Open"].iloc[-1]),
            "Volume": int(df["Volume"].iloc[-1]),
            "change_percent": round(change_pct, 2),
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "company": symbol,
        }
    except (KeyError, IndexError, TypeError):
        return None


def fetch_stock_data(ticker: str, use_mock_on_fail: bool = True) -> Optional[dict]:
    """
    Fetch ASX stock data. Uses yf.download only (no stock.info) to avoid rate limits.
    Falls back to mock data when Yahoo returns HTML/empty (blocked or rate limited).
    """
    symbol = ticker if ticker.endswith(".AX") else f"{ticker}.AX"
    try:
        data = yf.download(symbol, period="5d", progress=False, threads=False, auto_adjust=False)
        if data.empty or len(data) < 1:
            raise ValueError("Empty response")
        return _parse_ticker_from_download(data, symbol)
    except Exception:
        if use_mock_on_fail and os.getenv("USE_MOCK_STOCKS", "true").lower() == "true":
            return _mock_stock_data(symbol)
        return None


def fetch_multiple_stocks(tickers: list[str]) -> list[dict]:
    """
    Fetch multiple ASX stocks. Uses batch download, then sequential, then mock fallback.
    """
    symbols = [t if t.endswith(".AX") else f"{t}.AX" for t in tickers]
    if not symbols:
        return []

    try:
        data = yf.download(
            " ".join(symbols),
            period="5d",
            group_by="ticker",
            progress=False,
            threads=False,
            auto_adjust=False,
        )

        if data.empty:
            raise ValueError("Empty response")

        results = []
        if len(symbols) == 1:
            parsed = _parse_ticker_from_download(data, symbols[0])
            if parsed:
                results.append(parsed)
        elif isinstance(data.columns, pd.MultiIndex):
            for sym in symbols:
                try:
                    close_vals = data["Close"][sym] if sym in data["Close"].columns else None
                    if close_vals is None or len(close_vals) < 1:
                        continue
                    sub = pd.DataFrame({
                        "Open": data["Open"][sym],
                        "High": data["High"][sym],
                        "Low": data["Low"][sym],
                        "Close": data["Close"][sym],
                        "Volume": data["Volume"][sym],
                    })
                    parsed = _parse_ticker_from_download(sub, sym)
                    if parsed:
                        results.append(parsed)
                except (KeyError, TypeError):
                    pass
        else:
            parsed = _parse_ticker_from_download(data, symbols[0])
            if parsed:
                results.append(parsed)

        if results:
            return results
    except Exception:
        pass

    results = []
    for sym in symbols:
        d = fetch_stock_data(sym)
        if d:
            results.append(d)
        time.sleep(1)
    return results if results else [_mock_stock_data(s) for s in symbols]
