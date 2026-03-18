from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from app.collectors import fetch_financial_news, fetch_stock_data, fetch_multiple_stocks
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
