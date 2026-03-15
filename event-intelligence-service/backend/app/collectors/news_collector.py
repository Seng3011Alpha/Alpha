import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import requests

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search"
    "?q=ASX+Australian+stock+market+shares"
    "&hl=en-AU&gl=AU&ceid=AU:en"
)

REQUEST_TIMEOUT = 10
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Sources that produce clickbait/listicle content not useful for trading decisions
BLACKLIST_SOURCES = {
    "the motley fool",
    "the motley fool australia",
    "simply wall st",
    "simply wall street",
    "zacks investment research",
    "investing news network",
    "fool.com",
}

# Title keywords that indicate low-quality clickbait articles
FARM_KEYWORDS = [
    "top 5",
    "top 3",
    "top 10",
    "best stocks",
    "will it rise",
    "should you buy",
    "5 stocks",
    "3 stocks",
    "10 stocks",
    "shares to buy",
    "stocks to buy",
    "things to watch",
    "biggest companies",
]


def fetch_financial_news(page_size: int = 10) -> list[dict]:
    """
    Fetch Australian stock market news from Google News RSS.
    Filters out clickbait sources and farm content.
    No API key required. Falls back to mock data on failure.

    Args:
        page_size: Max number of quality articles to return
    """
    articles = _fetch_google_news_rss(page_size)
    return articles if articles else _mock_news()


def _fetch_google_news_rss(limit: int) -> list[dict]:
    """Fetch, parse, and filter Google News RSS feed."""
    try:
        response = requests.get(GOOGLE_NEWS_RSS, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        items = root.findall(".//item")

        articles = []
        # Scan more than limit to allow for filtered items
        for item in items[:limit * 3]:
            if len(articles) >= limit:
                break

            title = _text(item, "title")
            if not title:
                continue

            url = _clean_google_url(_text(item, "link"))
            pub_date = _parse_rss_date(_text(item, "pubDate"))
            source = _extract_source_name(item, title)
            description = _strip_html(_text(item, "description"))

            if _is_blacklisted(source) or _is_farm_content(title):
                continue

            articles.append({
                "title": title,
                "source": source,
                "url": url,
                "published_at": pub_date,
                "description": description,
            })

        return articles
    except Exception:
        return []


def _is_blacklisted(source: str) -> bool:
    """Return True if the source is in the blacklist."""
    return source.lower() in BLACKLIST_SOURCES


def _is_farm_content(title: str) -> bool:
    """Return True if the title contains clickbait/farm keywords."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in FARM_KEYWORDS)


def _text(element, tag: str) -> str:
    """Safely extract text from an XML element."""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_rss_date(date_str: str) -> str:
    """Convert RSS RFC 2822 date to ISO 8601."""
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _extract_source_name(item, title: str) -> str:
    """Extract source from <source> tag or title suffix '- Source Name'."""
    source_el = item.find("source")
    if source_el is not None and source_el.text:
        return source_el.text.strip()
    match = re.search(r" - ([^-]+)$", title)
    return match.group(1).strip() if match else "Google News"


def _clean_google_url(url: str) -> str:
    """Google RSS wraps articles in a redirect; return as-is for now."""
    return url


def _strip_html(text: str) -> str:
    """Remove HTML tags from description."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _mock_news() -> list[dict]:
    """Fallback when RSS fetch fails."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return [
        {
            "title": "ASX edges higher on mining and energy gains",
            "source": "MarketWatch",
            "url": "https://example.com/asx-gains",
            "published_at": now_iso,
            "description": "Australian shares rose as BHP and Woodside led broad-based gains.",
        },
        {
            "title": "RBA holds cash rate at 4.10%",
            "source": "AFR",
            "url": "https://example.com/rba-hold",
            "published_at": now_iso,
            "description": "Reserve Bank keeps rates on hold as inflation cools toward target band.",
        },
    ]
