import logging
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.collectors import fetch_financial_news, fetch_stock_data, fetch_multiple_stocks, fetch_stock_history
from app.observability import meter
from app.services import save_raw, save_standardised, analyse_sentiment_llm, extract_related_stocks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collect", tags=["Data Collection"])

PIPELINE_RUNS = meter.create_counter("pipeline_runs_total", description="Total pipeline executions")
STOCKS_FETCHED = meter.create_counter("stocks_fetched_total", description="Stocks fetched")
NEWS_COLLECTED = meter.create_counter("news_articles_collected_total", description="News articles collected")
STOCK_FAILURES = meter.create_counter("stock_fetch_failures_total", description="Stock fetch failures")
PIPELINE_DURATION = meter.create_histogram("pipeline_duration_seconds", description="Pipeline execution time")


@router.post("/stocks")
def collect_stocks(tickers: str | None = Query(None, description="Comma-separated: BHP,CBA,NAB")):
    #collect stock data for given asx tickers; defaults to bhp, cba, nab, wbc, anz
    default = ["BHP", "CBA", "NAB", "WBC", "ANZ"]
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()] if tickers else default
    data = fetch_multiple_stocks(ticker_list)
    if not data:
        for t in ticker_list:
            STOCK_FAILURES.add(1, {"ticker": t})
        logger.warning("stock_fetch_failed", extra={"tickers": ticker_list})
        raise HTTPException(status_code=503, detail="Failed to fetch stock data")
    for d in data:
        STOCKS_FETCHED.add(1, {"ticker": d["ticker"]})
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    save_raw(data, "stocks", f"stocks_{ts}.json")
    logger.info("stocks_collected", extra={"count": len(data), "tickers": [d["ticker"] for d in data]})
    return {"collected": len(data), "tickers": [d["ticker"] for d in data]}


@router.post("/news")
def collect_news():
    #collect australian stock market news from google news rss
    articles = fetch_financial_news()
    NEWS_COLLECTED.add(len(articles))
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    save_raw(articles, "news", f"news_{ts}.json")
    logger.info("news_collected", extra={"count": len(articles)})
    return {"collected": len(articles)}


@router.post("/history")
def collect_history(
    tickers: str | None = Query(None, description="Comma-separated: BHP,CBA,NAB"),
    period: str = Query("1mo", description="History period: 1mo, 3mo, 6mo, 1y"),
):
    
    allowed_periods = {"1mo", "3mo", "6mo", "1y"}
    if period not in allowed_periods:
        raise HTTPException(status_code=400, detail=f"period must be one of {allowed_periods}")

    default = ["BHP", "CBA", "NAB", "WBC", "ANZ"]
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()] if tickers else default

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    events = []
    collected = []

    for ticker in ticker_list:
        hist = fetch_stock_history(ticker, period=period)
        if not hist:
            STOCK_FAILURES.add(1, {"ticker": ticker.upper()})
            logger.warning("stock_history_fetch_failed", extra={"ticker": ticker, "period": period})
            continue

        collected.append(ticker.upper())
        sym = hist["quote"]["ticker"]
        STOCKS_FETCHED.add(1, {"ticker": sym})

        for row in hist["ohlc_series"]:
            events.append({
                "time_object": {"timestamp": row["date"], "timezone": "UTC"},
                "event_type": "Stock ohlc",
                "attribute": {
                    "ticker": sym,
                    "Open": row["Open"],
                    "High": row["High"],
                    "Low": row["Low"],
                    "Close": row["Close"],
                    "Adj Close": row["Adj Close"],
                    "Volume": row["Volume"],
                    "data_source": "yahoo_finance",
                },
            })

        ind = hist["indicators"]
        events.append({
            "time_object": {"timestamp": now, "timezone": "UTC"},
            "event_type": "Stock analysis",
            "attribute": {
                "ticker": sym,
                "MA5": ind["MA5"],
                "MA20": ind["MA20"],
                "volatility_annual_pct": ind["volatility_annual_pct"],
                "week52_high": ind["week52_high"],
                "week52_low": ind["week52_low"],
                "days_high": ind["days_high"],
                "days_low": ind["days_low"],
                "period": period,
                "data_source": "yahoo_finance",
            },
        })

    dataset = {
        "data_source": "event_intelligence",
        "dataset_type": "Daily stock data",
        "dataset_id": "s3://event-intelligence/history_events.json",
        "time_object": {"timestamp": now, "timezone": "UTC"},
        "events": events,
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    save_raw(dataset, "stocks", f"history_{ts}.json")
    save_standardised(dataset, "history_events.json")
    logger.info("history_collected", extra={"tickers": collected, "period": period, "events": len(events)})

    return {
        "tickers": collected,
        "period": period,
        "ohlc_events": sum(1 for e in events if e["event_type"] == "Stock ohlc"),
        "analysis_events": sum(1 for e in events if e["event_type"] == "Stock analysis"),
    }


@router.post("/pipeline")
def run_pipeline(
    tickers: str | None = Query(None, description="Comma-separated: BHP,CBA,NAB"),
):
    #run the full pipeline: collect stocks + news, analyse sentiment, save standardised
    default = ["BHP", "CBA", "NAB", "WBC", "ANZ"]
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()] if tickers else default

    logger.info("pipeline_started", extra={"tickers": ticker_list})
    PIPELINE_RUNS.add(1)
    _start = time.time()

    stocks = fetch_multiple_stocks(ticker_list)
    news = fetch_financial_news()

    for s in stocks:
        STOCKS_FETCHED.add(1, {"ticker": s.get("ticker", "unknown")})
    NEWS_COLLECTED.add(len(news))

    events = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    for s in stocks:
        events.append({
            "time_object": {"timestamp": now, "timezone": "UTC"},
            "event_type": "Stock quote",
            "attribute": {
                "ticker": s["ticker"],
                "Quote Price": s["Quote Price"],
                "Previous Close": s["Previous Close"],
                "Open": s["Open"],
                "Volume": s["Volume"],
                "change_percent": s["change_percent"],
                "data_source": "Yahoo finance",
            },
        })

    for n in news:
        text = f"{n.get('title', '')} {n.get('description', '')}"
        sentiment, score = analyse_sentiment_llm(text)
        related = extract_related_stocks(text, [t.replace(".AX", "") for t in ticker_list])
        events.append({
            "time_object": {"timestamp": now, "duration": 1, "duration_unit": "hour", "timezone": "UTC"},
            "event_type": "Stock news",
            "attribute": {
                "summary": n.get("title", ""),
                "title": n.get("title"),
                "link": n.get("url"),
                "published": n.get("published_at"),
                "source": n.get("source"),
                "region": "AU",
                "sentiment": sentiment,
                "impact_score": score,
                "related_stock": related[0] if related else None,
                "data_source": "google_news_rss",
            },
        })

    dataset = {
        "data_source": "event_intelligence",
        "dataset_type": "Mixed",
        "dataset_id": "s3://event-intelligence/combined_events.json",
        "time_object": {"timestamp": now, "timezone": "UTC"},
        "events": events,
    }

    save_standardised(dataset, "combined_events.json")

    _duration = round(time.time() - _start, 3)
    PIPELINE_DURATION.record(_duration)
    logger.info(
        "pipeline_complete",
        extra={
            "stocks_collected": len(stocks),
            "articles_collected": len(news),
            "events_total": len(events),
            "duration_seconds": _duration,
        },
    )
    return {"events_count": len(events), "stocks": len(stocks), "news": len(news)}
