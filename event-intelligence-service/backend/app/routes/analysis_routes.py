from fastapi import APIRouter, HTTPException, Query

from app.services import load_standardized

router = APIRouter(prefix="/api", tags=["Data Retrieval & Analysis"])


@router.get("/sentiment")
def get_sentiment(stock: str = Query(..., description="ASX ticker e.g. BHP or BHP.AX")):
    """
    Get sentiment and related data for a stock.
    Returns pre-processed data from standardized storage.
    """
    data = load_standardized("combined_events.json")
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
    """Get full combined events dataset."""
    data = load_standardized("combined_events.json")
    if not data:
        raise HTTPException(status_code=404, detail="No data available. Run /collect/pipeline first.")
    return data
