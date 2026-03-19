from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from app.collectors import fetch_financial_news, fetch_stock_data, fetch_multiple_stocks, fetch_stock_history
from app.services import save_raw, save_standardised, analyse_sentiment, extract_related_stocks

router = APIRouter(prefix="/collect", tags=["Data Collection"])


@router.post("/stocks")
def collect_stocks(tickers: str | None = Query(None, description="Comma-separated: BHP,CBA,NAB")):
    #collect stock data for given asx tickers; defaults to bhp, cba, nab, wbc, anz
    default = ["BHP", "CBA", "NAB", "WBC", "ANZ"]
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()] if tickers else default
    data = fetch_multiple_stocks(ticker_list)
    if not data:
        raise HTTPException(status_code=503, detail="Failed to fetch stock data")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    save_raw(data, "stocks", f"stocks_{ts}.json")
    return {"collected": len(data), "tickers": [d["ticker"] for d in data]}


@router.post("/news")
def collect_news():
    #collect australian stock market news from google news rss
    articles = fetch_financial_news()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    save_raw(articles, "news", f"news_{ts}.json")
    return {"collected": len(articles)}


@router.post("/history")
def collect_history(
    tickers: str | None = Query(None, description="Comma-separated: BHP,CBA,NAB"),
    period: str = Query("1mo", description="History period: 1mo, 3mo, 6mo, 1y"),
):
    """
    Collect historical OHLCV + indicators for given tickers and save as ADAGE events.
    Stores each day as a Stock ohlc event and indicators as a Stock analysis event.
    """
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
            continue

        collected.append(ticker.upper())
        sym = hist["quote"]["ticker"]

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

    stocks = fetch_multiple_stocks(ticker_list)
    news = fetch_financial_news()

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
        sentiment, score = analyse_sentiment(text)
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
    return {"events_count": len(events), "stocks": len(stocks), "news": len(news)}
