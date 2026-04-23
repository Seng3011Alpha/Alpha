import math
import os
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

from app.collectors.news_collector import fetch_financial_news
from app.collectors.stock_collector import fetch_stock_history
from app.services.analysis_service import analyse_sentiment


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = os.getenv("EXTERNAL_API_BASE_URL", "https://215fbbb9u9.execute-api.us-east-1.amazonaws.com")
TEST_EMAIL = os.getenv("EXTERNAL_API_TEST_EMAIL")
TEST_PASSWORD = os.getenv("EXTERNAL_API_TEST_PASSWORD")

TARGET_TICKER = os.getenv("EXTERNAL_API_DIVERGENCE_TICKER", "BHP")
TARGET_SUBREDDIT = os.getenv("EXTERNAL_API_DIVERGENCE_SUBREDDIT", "ASX_Bets")
TARGET_QUERY = os.getenv("EXTERNAL_API_DIVERGENCE_QUERY", "ASX BHP CBA NAB RBA")
LOOKBACK_DAYS = int(os.getenv("EXTERNAL_API_DIVERGENCE_LOOKBACK_DAYS", "14"))

MIN_ALIGNMENT_DAYS = int(os.getenv("EXTERNAL_API_DIVERGENCE_MIN_ALIGNMENT_DAYS", "2"))
MIN_CORRELATION_POINTS = int(os.getenv("EXTERNAL_API_DIVERGENCE_MIN_CORRELATION_POINTS", "3"))
MIN_FORMAL_ALIGNMENT_DAYS = int(os.getenv("EXTERNAL_API_DIVERGENCE_MIN_FORMAL_ALIGNMENT_DAYS", "5"))
NEUTRAL_BAND = float(os.getenv("EXTERNAL_API_DIVERGENCE_NEUTRAL_BAND", "0.12"))
PRICE_MOVE_THRESHOLD = float(os.getenv("EXTERNAL_API_DIVERGENCE_PRICE_MOVE_THRESHOLD", "0.02"))
SPIKE_MULTIPLIER = float(os.getenv("EXTERNAL_API_DIVERGENCE_SPIKE_MULTIPLIER", "1.5"))
MIN_TICKER_NEWS_DAYS = int(os.getenv("EXTERNAL_API_DIVERGENCE_MIN_TICKER_NEWS_DAYS", "3"))
SCENARIO_RAW = os.getenv(
    "EXTERNAL_API_DIVERGENCE_SCENARIOS",
    "ASX_Bets|ASX;ASX_Bets|BHP;ASX_Bets|CBA;australia|RBA;australia|ASX market",
)

ASX_KEYWORDS = ("asx", "australia", "australian", "rba", "bhp", "cba", "nab", "wbc", "anz", "rio", "wds")
TICKER_KEYWORDS = {
    "BHP": ("bhp", "bhp.ax"),
    "CBA": ("cba", "cba.ax", "commonwealth bank"),
    "NAB": ("nab", "nab.ax", "national australia bank"),
    "WBC": ("wbc", "wbc.ax", "westpac"),
    "ANZ": ("anz", "anz.ax"),
    "RIO": ("rio", "rio.ax", "rio tinto"),
    "WDS": ("wds", "wds.ax", "woodside"),
}


pytestmark = pytest.mark.skipif(
    not TEST_EMAIL or not TEST_PASSWORD,
    reason="Set EXTERNAL_API_TEST_EMAIL and EXTERNAL_API_TEST_PASSWORD to run divergence tests.",
)


def _to_date_key(value: str | int | float | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return None
    try:
        iso = text.replace("Z", "+00:00")
        return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _response_data(payload: dict) -> dict:
    nested = payload.get("data")
    return nested if isinstance(nested, dict) else payload


def _events(payload: dict) -> list[dict]:
    events = _response_data(payload).get("events")
    return events if isinstance(events, list) else []


def _login_token() -> str:
    response = requests.post(
        f"{BASE_URL}/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=20,
    )
    response.raise_for_status()
    token = response.json().get("token") or response.json().get("access_token")
    assert token, "Login succeeded but no token/access_token was returned."
    return token


def _parse_scenarios() -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for part in SCENARIO_RAW.split(";"):
        raw = part.strip()
        if not raw or "|" not in raw:
            continue
        subreddit, query = [x.strip() for x in raw.split("|", 1)]
        if subreddit and query:
            parsed.append((subreddit, query))
    if not parsed:
        parsed.append((TARGET_SUBREDDIT, TARGET_QUERY))
    return parsed


def _fetch_reddit_posts(subreddit: str, query: str, token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    after_date = (datetime.now(timezone.utc) - timedelta(days=max(LOOKBACK_DAYS, 7))).strftime("%Y-%m-%d")
    response = requests.get(
        f"{BASE_URL}/v1/post/search",
        params={
            "query": query,
            "subreddit": subreddit,
            "limit": 100,
            "after": after_date,
        },
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    events = _events(response.json())
    if events:
        return events

    fallback_response = requests.get(
        f"{BASE_URL}/v1/post/search",
        params={
            "query": query,
            "subreddit": subreddit,
            "limit": 100,
        },
        headers=headers,
        timeout=30,
    )
    fallback_response.raise_for_status()
    return _events(fallback_response.json())


def _text_sentiment_value(sentiment: str, score: float) -> float:
    if sentiment == "positive":
        return score
    if sentiment == "negative":
        return -score
    return 0.0


def _is_relevant_text(text: str, ticker: str) -> bool:
    lowered = text.lower()
    ticker_terms = TICKER_KEYWORDS.get(ticker.upper(), (ticker.lower(),))
    return any(k in lowered for k in ASX_KEYWORDS) or any(term in lowered for term in ticker_terms)


def _aggregate_reddit_daily(events: list[dict], ticker: str) -> dict[str, dict]:
    per_day: dict[str, dict] = defaultdict(lambda: {"sentiments": [], "weighted_sum": 0.0, "weight": 0.0, "volume": 0})
    for event in events:
        attributes = event.get("attributes", {})
        created_utc = attributes.get("created_utc")
        day_key = _to_date_key(created_utc)
        if not day_key:
            continue
        title = str(attributes.get("title", ""))
        body = str(attributes.get("selftext", ""))
        merged_text = f"{title} {body}".strip()
        if not _is_relevant_text(merged_text, ticker):
            continue
        sentiment, score = analyse_sentiment(merged_text)
        sentiment_value = _text_sentiment_value(sentiment, score)
        reddit_score = float(attributes.get("score") or 0.0)
        weight = max(1.0, math.log1p(max(0.0, reddit_score)))
        bucket = per_day[day_key]
        bucket["sentiments"].append(sentiment_value)
        bucket["weighted_sum"] += sentiment_value * weight
        bucket["weight"] += weight
        bucket["volume"] += 1
    return per_day


def _aggregate_news_daily(ticker: str) -> dict[str, dict]:
    ticker_day: dict[str, dict] = defaultdict(lambda: {"sentiments": [], "volume": 0})
    broad_day: dict[str, dict] = defaultdict(lambda: {"sentiments": [], "volume": 0})
    articles = fetch_financial_news(page_size=300)
    ticker_terms = TICKER_KEYWORDS.get(ticker.upper(), (ticker.lower(),))

    for article in articles:
        title = str(article.get("title", ""))
        description = str(article.get("description", ""))
        merged_text = f"{title} {description}".strip()
        day_key = _to_date_key(article.get("published_at"))
        if not day_key:
            continue
        lowered = merged_text.lower()
        if any(term in lowered for term in ticker_terms):
            sentiment, score = analyse_sentiment(merged_text)
            sentiment_value = _text_sentiment_value(sentiment, score)
            bucket = ticker_day[day_key]
            bucket["sentiments"].append(sentiment_value)
            bucket["volume"] += 1
        if any(k in lowered for k in ASX_KEYWORDS):
            sentiment, score = analyse_sentiment(merged_text)
            sentiment_value = _text_sentiment_value(sentiment, score)
            broad_bucket = broad_day[day_key]
            broad_bucket["sentiments"].append(sentiment_value)
            broad_bucket["volume"] += 1

    return ticker_day if len(ticker_day) >= MIN_TICKER_NEWS_DAYS else broad_day


def _stock_returns_by_day(ticker: str, period_days: int) -> dict[str, float]:
    if period_days <= 31:
        period = "1mo"
    elif period_days <= 92:
        period = "3mo"
    else:
        period = "6mo"
    history = fetch_stock_history(ticker, period=period)
    if not history:
        return {}
    series = history.get("ohlc_series", [])
    returns: dict[str, float] = {}
    for row in series:
        open_price = row.get("Open")
        close_price = row.get("Close")
        date_key = row.get("date")
        if not date_key or open_price in (None, 0) or close_price is None:
            continue
        returns[date_key] = (float(close_price) - float(open_price)) / float(open_price)
    return returns


def _pearson(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return float("nan")
    x_mean = statistics.mean(x)
    y_mean = statistics.mean(y)
    num = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y))
    den_x = math.sqrt(sum((a - x_mean) ** 2 for a in x))
    den_y = math.sqrt(sum((b - y_mean) ** 2 for b in y))
    if den_x == 0 or den_y == 0:
        return float("nan")
    return num / (den_x * den_y)


def _aligned_series_for_reddit_daily(
    reddit_daily: dict[str, dict],
    news_daily: dict[str, dict],
    returns_daily: dict[str, float],
) -> tuple[list[str], list[float], list[float], list[float], list[int]]:
    common_days = sorted(set(reddit_daily.keys()) & set(news_daily.keys()) & set(returns_daily.keys()))

    reddit_sent: list[float] = []
    news_sent: list[float] = []
    day_returns: list[float] = []
    reddit_volume: list[int] = []
    for day in common_days:
        r = reddit_daily[day]
        n = news_daily[day]
        r_sent = (r["weighted_sum"] / r["weight"]) if r["weight"] else 0.0
        n_sent = statistics.mean(n["sentiments"]) if n["sentiments"] else 0.0
        reddit_sent.append(r_sent)
        news_sent.append(n_sent)
        day_returns.append(returns_daily[day])
        reddit_volume.append(int(r["volume"]))
    return common_days, news_sent, reddit_sent, day_returns, reddit_volume


def _best_aligned_series() -> tuple[list[str], list[float], list[float], list[float], list[int], str]:
    token = _login_token()
    scenarios = _parse_scenarios()
    news_daily = _aggregate_news_daily(TARGET_TICKER)
    returns_daily = _stock_returns_by_day(TARGET_TICKER, LOOKBACK_DAYS)

    best: tuple[list[str], list[float], list[float], list[float], list[int], str] = ([], [], [], [], [], "")
    for subreddit, query in scenarios:
        reddit_events = _fetch_reddit_posts(subreddit, query, token)
        reddit_daily = _aggregate_reddit_daily(reddit_events, TARGET_TICKER)
        days, news_sent, reddit_sent, day_returns, reddit_volume = _aligned_series_for_reddit_daily(
            reddit_daily, news_daily, returns_daily
        )
        scenario_label = f"{subreddit}|{query}"
        if len(days) > len(best[0]):
            best = (days, news_sent, reddit_sent, day_returns, reddit_volume, scenario_label)

    return best


def test_step1_data_alignment_for_asx_ticker():
    days, news_sent, reddit_sent, day_returns, reddit_volume, scenario_used = _best_aligned_series()
    if len(days) < MIN_ALIGNMENT_DAYS:
        pytest.skip(
            f"Not enough aligned days for {TARGET_TICKER} (got {len(days)}). "
            f"Best scenario: {scenario_used}. Increase lookback or broaden subreddit/query."
        )
    assert len(news_sent) == len(reddit_sent) == len(day_returns) == len(reddit_volume) == len(days)


def test_step2_anomaly_detection_reddit_vs_neutral_news():
    days, news_sent, _, day_returns, reddit_volume, _ = _best_aligned_series()
    if len(days) < MIN_ALIGNMENT_DAYS:
        pytest.skip("Not enough aligned days to evaluate anomaly detection.")

    baseline_volume = statistics.median(reddit_volume) if reddit_volume else 0
    anomalies = []
    for idx, day in enumerate(days):
        neutral_news = abs(news_sent[idx]) <= NEUTRAL_BAND
        large_move = abs(day_returns[idx]) >= PRICE_MOVE_THRESHOLD
        volume_spike = reddit_volume[idx] >= max(2, baseline_volume * SPIKE_MULTIPLIER)
        if neutral_news and large_move:
            anomalies.append((day, volume_spike))

    if not anomalies:
        pytest.skip("No neutral-news + large-move days in current sample window.")

    assert any(spike for _, spike in anomalies), (
        "Detected anomaly days, but none had a Reddit volume spike. "
        "This suggests weak social-signal amplification in the sampled period."
    )


def test_step3_pearson_and_lag_correlation():
    days, news_sent, reddit_sent, _, _, scenario_used = _best_aligned_series()
    if len(days) < MIN_FORMAL_ALIGNMENT_DAYS:
        pytest.skip(
            f"Formal correlation requires >= {MIN_FORMAL_ALIGNMENT_DAYS} aligned days, "
            f"got {len(days)} (best scenario: {scenario_used})."
        )
    if len(days) < MIN_CORRELATION_POINTS:
        pytest.skip("Not enough aligned days to compute reliable correlation.")

    same_day_r = _pearson(news_sent, reddit_sent)
    assert not math.isnan(same_day_r), "Pearson correlation produced NaN (insufficient variance)."
    assert -1.0 <= same_day_r <= 1.0

    if len(days) >= MIN_CORRELATION_POINTS + 1:
        lag1_r = _pearson(reddit_sent[:-1], news_sent[1:])
        assert not math.isnan(lag1_r), "Lag-1 correlation produced NaN."
        assert -1.0 <= lag1_r <= 1.0
