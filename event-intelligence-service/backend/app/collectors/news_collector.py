import os
from datetime import datetime
from typing import Optional

from newsapi import NewsApiClient


def fetch_financial_news(
    api_key: Optional[str] = None,
    page_size: int = 10,
) -> list[dict]:
    """
    Fetch Australian business headlines. Requires NEWS_API_KEY in environment.
    Free tier: 100 requests/day.
    """
    key = api_key or os.getenv("NEWS_API_KEY")
    if not key:
        return _mock_news()

    try:
        client = NewsApiClient(api_key=key)
        response = client.get_everything(
            sources="afr",
            page_size=min(page_size, 20),
        )
        print(response)
        articles = response.get("articles", [])
        print(articles)
        return [
            {
                "title": a.get("title", ""),
                "source": a.get("source", {}).get("name", "Unknown"),
                "url": a.get("url", ""),
                "published_at": a.get("publishedAt", ""),
                "description": a.get("description", "") or "",
            }
            for a in articles
            if a.get("title") != "[Removed]"
        ]
    except Exception:
        return _mock_news()


def _mock_news() -> list[dict]:
    """Fallback when API key is missing or request fails."""
    return [
        {
            "title": "ASX gains on commodity strength",
            "source": "AFR",
            "url": "https://example.com/1",
            "published_at": datetime.utcnow().isoformat() + "Z",
            "description": "Australian shares rose as mining stocks led gains.",
        },
        {
            "title": "RBA holds rates steady",
            "source": "Reuters",
            "url": "https://example.com/2",
            "published_at": datetime.utcnow().isoformat() + "Z",
            "description": "Reserve Bank keeps interest rates unchanged.",
        },
    ]
