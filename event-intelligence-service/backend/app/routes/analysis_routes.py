from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.collectors import fetch_financial_news, fetch_stock_data, fetch_stock_history
from app.services import load_standardised, analyse_sentiment_llm, extract_related_stocks
from app.services.report_service import generate_stock_report

router = APIRouter(prefix="/api", tags=["Data Retrieval & Analysis"])


def _normalise(ticker: str) -> str:
    t = ticker.upper()
    return t if t.endswith(".AX") else f"{t}.AX"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# /api/news
# ---------------------------------------------------------------------------

@router.get("/news")
def get_news(
    ticker: str | None = Query(None, description="ASX ticker e.g. BHP or BHP.AX. Omit for all news."),
    limit: int = Query(20, description="Max articles to return", ge=1, le=100),
):
    """
    Return news events in ADAGE format.
    Reads from cache (combined_events.json) if available; otherwise fetches live from Google News RSS.
    """
    now = _now_iso()
    sym = _normalise(ticker) if ticker else None

    cached = load_standardised("combined_events.json")
    if cached:
        all_news = [e for e in cached["events"] if e["event_type"] == "Stock news"]
        if sym:
            matched = [e for e in all_news if e["attribute"].get("related_stock") == sym]
            general = [e for e in all_news if not e["attribute"].get("related_stock")]
            news_events = matched + general[:max(0, limit - len(matched))]
        else:
            news_events = all_news

        return {
            "data_source": cached.get("data_source"),
            "dataset_type": cached.get("dataset_type"),
            "dataset_id": cached.get("dataset_id"),
            "time_object": cached.get("time_object"),
            "cached": True,
            "events": [
                {"time_object": e["time_object"], "event_type": e["event_type"], "attribute": e["attribute"]}
                for e in news_events[:limit]
            ],
            "total": min(len(news_events), limit),
        }

    # No cache — live fetch
    articles = fetch_financial_news()
    tickers_ref = [sym] if sym else []
    events = []
    for a in articles[:limit]:
        text = f"{a.get('title', '')} {a.get('description', '')}"
        sentiment, score = analyse_sentiment_llm(text)
        related = extract_related_stocks(text, [sym.replace(".AX", "")] if sym else [])
        events.append({
            "time_object": {"timestamp": a.get("published_at", now), "duration": 1, "duration_unit": "hour", "timezone": "UTC"},
            "event_type": "Stock news",
            "attribute": {
                "title": a.get("title"),
                "summary": text.strip(),
                "link": a.get("url"),
                "published": a.get("published_at"),
                "source": a.get("source"),
                "region": "AU",
                "sentiment": sentiment,
                "impact_score": score,
                "related_stock": related[0] if related else None,
                "data_source": "google_news_rss",
            },
        })

    return {
        "data_source": "event_intelligence",
        "dataset_type": "financial_news",
        "dataset_id": "live",
        "time_object": {"timestamp": now, "timezone": "UTC"},
        "cached": False,
        "events": events,
        "total": len(events),
    }


# ---------------------------------------------------------------------------
# /api/stock
# ---------------------------------------------------------------------------

@router.get("/stock")
def get_stock(
    ticker: str = Query(..., description="ASX ticker e.g. BHP or BHP.AX"),
    include_ohlc: bool = Query(False, description="Include full historical OHLC series and indicators"),
):
    """
    Return stock quote in ADAGE format.
    Reads from cache if available; otherwise fetches live from Yahoo Finance.
    If include_ohlc=true, also returns historical OHLCV + indicators (always live if no history cache).
    """
    sym = _normalise(ticker)
    now = _now_iso()

    quote_event = None
    combined = load_standardised("combined_events.json")
    if combined:
        matches = [
            e for e in combined["events"]
            if e["event_type"] == "Stock quote" and e["attribute"].get("ticker") == sym
        ]
        if matches:
            quote_event = matches[0]

    if not quote_event:
        live = fetch_stock_data(sym)
        if not live:
            raise HTTPException(status_code=503, detail=f"Could not retrieve data for {sym}.")
        quote_event = {
            "time_object": {"timestamp": now, "timezone": "UTC"},
            "event_type": "Stock quote",
            "attribute": live,
        }

    response = {
        "data_source": "Yahoo Finance",
        "dataset_type": "Daily stock data",
        "dataset_id": f"s3://event-intelligence/combined_events.json",
        "time_object": combined.get("time_object") if combined else {"timestamp": now, "timezone": "UTC"},
        "cached": combined is not None,
        "events": [quote_event],
    }

    if include_ohlc:
        history = load_standardised("history_events.json")
        ohlc_events = []
        analysis_events = []

        if history:
            ohlc_events = [e for e in history["events"] if e["event_type"] == "Stock ohlc" and e["attribute"].get("ticker") == sym]
            analysis_events = [e for e in history["events"] if e["event_type"] == "Stock analysis" and e["attribute"].get("ticker") == sym]

        if not ohlc_events:
            live_hist = fetch_stock_history(sym, period="1mo")
            if live_hist:
                for row in live_hist["ohlc_series"]:
                    ohlc_events.append({
                        "time_object": {"timestamp": row["date"], "timezone": "UTC"},
                        "event_type": "Stock ohlc",
                        "attribute": {"ticker": sym, **{k: v for k, v in row.items() if k != "date"}, "data_source": "yahoo_finance"},
                    })
                ind = live_hist["indicators"]
                analysis_events = [{
                    "time_object": {"timestamp": now, "timezone": "UTC"},
                    "event_type": "Stock analysis",
                    "attribute": {"ticker": sym, **ind, "period": "1mo", "data_source": "yahoo_finance"},
                }]

        ohlc_sorted = sorted(ohlc_events, key=lambda x: x["time_object"].get("timestamp", ""))
        response["events"] += ohlc_sorted + analysis_events
        response["ohlc_data_points"] = len(ohlc_sorted)

    return response


# ---------------------------------------------------------------------------
# /api/analysis
# ---------------------------------------------------------------------------

@router.get("/analysis")
def get_analysis(
    stock: str = Query(..., description="ASX ticker e.g. BHP or BHP.AX"),
    period: str = Query("1mo", description="1mo, 3mo, 6mo, 1y — only used for live fetch"),
):
    """
    Return historical OHLCV + indicators (MA5, MA20, volatility, 52w high/low).
    Reads from history cache if available; otherwise fetches live.
    """
    ticker = _normalise(stock)
    now = _now_iso()

    cached = load_standardised("history_events.json")
    if cached:
        ohlc = [e["attribute"] for e in cached["events"] if e["event_type"] == "Stock ohlc" and e["attribute"].get("ticker") == ticker]
        analysis_events = [e["attribute"] for e in cached["events"] if e["event_type"] == "Stock analysis" and e["attribute"].get("ticker") == ticker]
        if ohlc or analysis_events:
            ohlc_sorted = sorted(ohlc, key=lambda x: x.get("date", ""))
            return {
                "stock": ticker,
                "period": analysis_events[0].get("period") if analysis_events else None,
                "indicators": {k: v for k, v in analysis_events[0].items() if k not in ("ticker", "data_source", "period")} if analysis_events else None,
                "ohlc_series": [{k: v for k, v in row.items() if k not in ("ticker", "data_source")} for row in ohlc_sorted],
                "data_points": len(ohlc_sorted),
                "cached": True,
            }

    # No cache — live fetch
    hist = fetch_stock_history(ticker, period=period)
    if not hist:
        raise HTTPException(status_code=503, detail=f"Could not retrieve history for {ticker}.")

    return {
        "stock": ticker,
        "period": hist["period"],
        "indicators": hist["indicators"],
        "ohlc_series": hist["ohlc_series"],
        "data_points": len(hist["ohlc_series"]),
        "cached": False,
    }


# ---------------------------------------------------------------------------
# /api/sentiment
# ---------------------------------------------------------------------------

@router.get("/sentiment")
def get_sentiment(stock: str = Query(..., description="ASX ticker e.g. BHP or BHP.AX")):
    """
    Return overall sentiment + related news for a ticker.
    Falls back to live news fetch if no pipeline cache exists.
    """
    sym = _normalise(stock)
    now = _now_iso()

    data = load_standardised("combined_events.json")
    if data:
        stock_events = [e for e in data["events"] if e["event_type"] == "Stock quote" and e["attribute"].get("ticker") == sym]
        news_events = [e for e in data["events"] if e["event_type"] == "Stock news" and e["attribute"].get("related_stock") == sym]
        general_news = [e for e in data["events"] if e["event_type"] == "Stock news" and not e["attribute"].get("related_stock")]
        if not news_events:
            news_events = general_news[:5]
        stock_data = stock_events[0]["attribute"] if stock_events else None
        cached = True
    else:
        live = fetch_stock_data(sym)
        stock_data = live
        articles = fetch_financial_news()
        news_events = []
        for a in articles[:10]:
            text = f"{a.get('title', '')} {a.get('description', '')}"
            sentiment, score = analyse_sentiment_llm(text)
            related = extract_related_stocks(text, [sym.replace(".AX", "")])
            news_events.append({
                "attribute": {
                    "title": a.get("title"),
                    "sentiment": sentiment,
                    "impact_score": score,
                    "related_stock": related[0] if related else None,
                }
            })
        cached = False

    return {
        "stock": sym,
        "cached": cached,
        "stock_data": stock_data,
        "related_news": [
            {"title": n["attribute"].get("title", "")[:120], "sentiment": n["attribute"]["sentiment"], "impact_score": n["attribute"]["impact_score"]}
            for n in news_events[:10]
        ],
        "overall_sentiment": _aggregate_sentiment(news_events) if news_events else "neutral",
    }


def _aggregate_sentiment(news_events: list) -> str:
    sentiments = [e["attribute"].get("sentiment", "neutral") for e in news_events]
    pos = sum(1 for s in sentiments if s == "positive")
    neg = sum(1 for s in sentiments if s == "negative")
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


# ---------------------------------------------------------------------------
# /api/events
# ---------------------------------------------------------------------------

@router.get("/events")
def get_events():
    """Return the full combined events dataset. Requires /collect/pipeline to have been run."""
    data = load_standardised("combined_events.json")
    if not data:
        raise HTTPException(status_code=404, detail="No data available. Run POST /collect/pipeline first.")
    return data


# ---------------------------------------------------------------------------
# /api/report
# ---------------------------------------------------------------------------

@router.get("/report")
def get_report(
    stock: str = Query(..., description="ASX ticker e.g. BHP or BHP.AX"),
    force_refresh: bool = Query(False, description="Bypass the daily cache"),
):
    """Return an analyst-style written report synthesised by Claude from quote, news, indicators."""
    sym = _normalise(stock)
    now = _now_iso()

    combined = load_standardised("combined_events.json")
    quote_attr: dict | None = None
    news_attrs: list[dict] = []
    if combined:
        for e in combined["events"]:
            if e["event_type"] == "Stock quote" and e["attribute"].get("ticker") == sym and quote_attr is None:
                quote_attr = e["attribute"]
            elif e["event_type"] == "Stock news" and e["attribute"].get("related_stock") == sym:
                news_attrs.append(e["attribute"])
        if len(news_attrs) < 5:
            general = [e["attribute"] for e in combined["events"] if e["event_type"] == "Stock news" and not e["attribute"].get("related_stock")]
            news_attrs = (news_attrs + general)[:15]

    if not quote_attr:
        live = fetch_stock_data(sym)
        if live:
            quote_attr = live

    if not news_attrs:
        articles = fetch_financial_news()
        for a in articles[:15]:
            text = f"{a.get('title', '')} {a.get('description', '')}"
            sentiment, score = analyse_sentiment_llm(text)
            news_attrs.append({
                "title": a.get("title"),
                "source": a.get("source"),
                "link": a.get("url"),
                "published": a.get("published_at"),
                "sentiment": sentiment,
                "impact_score": score,
            })

    indicators: dict | None = None
    history = load_standardised("history_events.json")
    if history:
        for e in history["events"]:
            if e["event_type"] == "Stock analysis" and e["attribute"].get("ticker") == sym:
                indicators = {k: v for k, v in e["attribute"].items() if k not in ("ticker", "data_source", "period")}
                break

    if indicators is None:
        live_hist = fetch_stock_history(sym, period="1mo")
        if live_hist:
            indicators = live_hist["indicators"]

    return generate_stock_report(
        ticker=sym,
        quote=quote_attr,
        news=news_attrs[:15],
        indicators=indicators,
        force_refresh=force_refresh,
    )
