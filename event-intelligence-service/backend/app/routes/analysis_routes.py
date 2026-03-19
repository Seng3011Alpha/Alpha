from fastapi import APIRouter, HTTPException, Query

from app.services import load_standardised

router = APIRouter(prefix="/api", tags=["Data Retrieval & Analysis"])


@router.get("/analysis")
def get_analysis(stock: str = Query(..., description="ASX ticker e.g. BHP or BHP.AX")):
    """
    Return historical OHLCV series and computed indicators (MA5, MA20, volatility,
    52w high/low, day's range) for a stock from the last /collect/history run.
    """
    data = load_standardised("history_events.json")
    if not data:
        raise HTTPException(
            status_code=404,
            detail="No history available. Run POST /collect/history first.",
        )

    ticker = stock.upper()
    if not ticker.endswith(".AX"):
        ticker = f"{ticker}.AX"

    ohlc = [
        e["attribute"]
        for e in data["events"]
        if e["event_type"] == "Stock ohlc" and e["attribute"].get("ticker") == ticker
    ]
    analysis_events = [
        e["attribute"]
        for e in data["events"]
        if e["event_type"] == "Stock analysis" and e["attribute"].get("ticker") == ticker
    ]

    if not ohlc and not analysis_events:
        raise HTTPException(status_code=404, detail=f"No history found for {ticker}.")

    ohlc_sorted = sorted(ohlc, key=lambda x: x.get("date", "")) if ohlc else []

    return {
        "stock": ticker,
        "period": analysis_events[0].get("period") if analysis_events else None,
        "indicators": {k: v for k, v in analysis_events[0].items() if k not in ("ticker", "data_source", "period")} if analysis_events else None,
        "ohlc_series": [
            {k: v for k, v in row.items() if k not in ("ticker", "data_source")}
            for row in ohlc_sorted
        ],
        "data_points": len(ohlc_sorted),
    }


@router.get("/sentiment")
def get_sentiment(stock: str = Query(..., description="ASX ticker e.g. BHP or BHP.AX")):
    #get sentiment and stock data for a ticker from standardised storage
    data = load_standardised("combined_events.json")
    if not data:
        raise HTTPException(status_code=404, detail="No data available. Run /collect/pipeline first.")

    ticker = stock.upper() if not stock.upper().endswith(".AX") else stock.upper()
    if not ticker.endswith(".AX"):
        ticker = f"{ticker}.AX"

    stock_events = [e for e in data["events"] if e["event_type"] == "Stock quote" and e["attribute"].get("ticker") == ticker]
    news_events = [e for e in data["events"] if e["event_type"] == "Stock news" and e["attribute"].get("related_stock") == ticker]
    general_news = [e for e in data["events"] if e["event_type"] == "Stock news" and not e["attribute"].get("related_stock")]

    if not stock_events and not news_events:
        news_events = general_news[:5]

    return {
        "stock": ticker,
        "stock_data": stock_events[0]["attribute"] if stock_events else None,
        "related_news": [
            {"title": n["attribute"].get("title") or n["attribute"].get("summary", "")[:100], "sentiment": n["attribute"]["sentiment"], "impact_score": n["attribute"]["impact_score"]}
            for n in news_events[:10]
        ],
        "overall_sentiment": _aggregate_sentiment(news_events) if news_events else "neutral",
    }


def _aggregate_sentiment(news_events: list) -> str:
    scores = [e["attribute"].get("impact_score", 0.5) for e in news_events]
    sentiments = [e["attribute"].get("sentiment", "neutral") for e in news_events]
    pos = sum(1 for s in sentiments if s == "positive")
    neg = sum(1 for s in sentiments if s == "negative")
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


@router.get("/events")
def get_events():
    #return the full combined events dataset from standardised storage
    data = load_standardised("combined_events.json")
    if not data:
        raise HTTPException(status_code=404, detail="No data available. Run /collect/pipeline first.")
    return data
