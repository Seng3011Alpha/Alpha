import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import requests

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-AU&gl=AU&ceid=AU:en"

#multiple search queries to spread across the rss limit and cover more ground
RSS_QUERIES = [
    "ASX+Australian+stock+market+shares",
    "ASX+200+shares",
    "BHP+CBA+NAB+ASX",
    "Australian+mining+energy+stocks",
    "RBA+interest+rates+ASX",
]

REQUEST_TIMEOUT = 10
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

#sources that produce clickbait or listicle content - not useful for trading decisions
BLACKLIST_SOURCES = {
    "the motley fool",
    "the motley fool australia",
    "simply wall st",
    "simply wall street",
    "zacks investment research",
    "investing news network",
    "fool.com",
}

#title keywords that indicate low-quality clickbait articles
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


def fetch_financial_news(page_size: int = 500) -> list[dict]:
    #fetch australian stock market news from google news rss; falls back to mock on failure
    articles = _fetch_google_news_rss(page_size)
    return articles if articles else _mock_news()


def _fetch_google_news_rss(limit: int) -> list[dict]:
    #query multiple rss feeds and deduplicate by url to work around google's ~100 item cap per feed
    seen_urls: set[str] = set()
    articles: list[dict] = []

    for query in RSS_QUERIES:
        if len(articles) >= limit:
            break
        url = GOOGLE_NEWS_RSS.format(query=query)
        batch = _fetch_single_rss(url, limit - len(articles), seen_urls)
        articles.extend(batch)

    return articles


def _fetch_single_rss(url: str, remaining: int, seen_urls: set[str]) -> list[dict]:
    #fetch, parse and filter one rss feed url; updates seen_urls in place
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        items = root.findall(".//item")

        articles = []
        #scan more items than remaining to account for blacklisted/farm/duplicate ones
        for item in items[:remaining * 3]:
            if len(articles) >= remaining:
                break

            title = _text(item, "title")
            if not title:
                continue

            article_url = _clean_google_url(_text(item, "link"))
            if article_url in seen_urls:
                continue

            pub_date = _parse_rss_date(_text(item, "pubDate"))
            source = _extract_source_name(item, title)
            description = _strip_html(_text(item, "description"))

            if _is_blacklisted(source) or _is_farm_content(title):
                continue

            seen_urls.add(article_url)
            articles.append({
                "title": title,
                "source": source,
                "url": article_url,
                "published_at": pub_date,
                "description": description,
            })

        return articles
    except Exception:
        return []


def _is_blacklisted(source: str) -> bool:
    #return true if the source appears in the blacklist set
    return source.lower() in BLACKLIST_SOURCES


def _is_farm_content(title: str) -> bool:
    #return true if the title contains clickbait or content farm keywords
    title_lower = title.lower()
    return any(kw in title_lower for kw in FARM_KEYWORDS)


def _text(element, tag: str) -> str:
    #safely extract text from an xml element, returning empty string if missing
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_rss_date(date_str: str) -> str:
    #convert rss rfc 2822 date string to iso 8601
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _extract_source_name(item, title: str) -> str:
    #extract source from the <source> tag or from the ' - source name' title suffix
    source_el = item.find("source")
    if source_el is not None and source_el.text:
        return source_el.text.strip()
    match = re.search(r" - ([^-]+)$", title)
    return match.group(1).strip() if match else "Google News"


def _clean_google_url(url: str) -> str:
    #google rss wraps articles in a redirect url; returned as-is for now
    return url


def _strip_html(text: str) -> str:
    #strip html tags and decode html entities (e.g. &nbsp;) from description text
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def _mock_news() -> list[dict]:
    #Fallback when RSS fetch fails.
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
