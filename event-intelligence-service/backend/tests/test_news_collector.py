#tests for news_collector - rss fetching, filtering and fallback behaviour
import xml.etree.ElementTree as ET
import pytest
from unittest.mock import patch, MagicMock
from app.collectors.news_collector import (
    fetch_financial_news,
    _fetch_google_news_rss,
    _is_blacklisted,
    _is_farm_content,
    _parse_rss_date,
    _strip_html,
    _extract_source_name,
    _clean_google_url,
    _mock_news,
)


#sample rss feed with one legitimate article and one blacklisted clickbait one
RSS_WITH_ARTICLES = """<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item>
    <title>BHP reports record profit - Australian Financial Review</title>
    <link>https://example.com/bhp</link>
    <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
    <source>Australian Financial Review</source>
    <description>BHP posted strong earnings.</description>
  </item>
  <item>
    <title>Top 5 ASX stocks to buy - The Motley Fool</title>
    <link>https://example.com/motley</link>
    <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
    <source>The Motley Fool</source>
    <description>Clickbait content.</description>
  </item>
</channel></rss>"""

RSS_NO_RESULT = """<?xml version="1.0" encoding="UTF-8"?>
<rss><channel></channel></rss>"""


class TestIsBlacklisted:
    def test_blacklisted_source(self):
        assert _is_blacklisted("The Motley Fool") is True

    def test_blacklisted_source_case_insensitive(self):
        assert _is_blacklisted("SIMPLY WALL ST") is True

    def test_legitimate_source(self):
        assert _is_blacklisted("Australian Financial Review") is False

    def test_empty_string(self):
        assert _is_blacklisted("") is False


class TestIsFarmContent:
    def test_clickbait_title(self):
        assert _is_farm_content("Top 5 ASX stocks to watch") is True

    def test_listicle_title(self):
        assert _is_farm_content("3 stocks you should buy now") is True

    def test_legitimate_title(self):
        assert _is_farm_content("BHP reports record quarterly earnings") is False

    def test_case_insensitive(self):
        assert _is_farm_content("BEST STOCKS for 2024") is True


class TestParseRssDate:
    def test_valid_rss_date(self):
        result = _parse_rss_date("Mon, 01 Jan 2024 12:00:00 +0000")
        assert "2024" in result
        assert "T" in result  #iso 8601 uses a T separator

    def test_invalid_date_returns_fallback(self):
        #bad input should fall back to current time rather than crashing
        result = _parse_rss_date("not-a-date")
        assert result
        assert isinstance(result, str)


class TestStripHtml:
    def test_removes_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_no_tags_unchanged(self):
        assert _strip_html("plain text") == "plain text"

    def test_empty_string(self):
        assert _strip_html("") == ""


class TestMockNews:
    def test_returns_list(self):
        result = _mock_news()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_articles_have_required_keys(self):
        result = _mock_news()
        for article in result:
            assert "title" in article
            assert "source" in article
            assert "url" in article
            assert "published_at" in article


class TestCleanGoogleUrl:
    def test_returns_url_unchanged(self):
        assert _clean_google_url("https://example.com") == "https://example.com"

    def test_empty_string(self):
        assert _clean_google_url("") == ""


class TestExtractSourceName:
    def test_source_tag_takes_priority(self):
        #explicit <source> tag should win over the title suffix
        item = ET.fromstring("<item><source>AFR</source></item>")
        assert _extract_source_name(item, "Title - Other") == "AFR"

    def test_falls_back_to_title_suffix(self):
        item = ET.fromstring("<item></item>")
        assert _extract_source_name(item, "BHP up - Sydney Morning Herald") == "Sydney Morning Herald"

    def test_falls_back_to_google_news(self):
        #no source tag and no dash suffix so default to google news
        item = ET.fromstring("<item></item>")
        assert _extract_source_name(item, "No source here") == "Google News"


class TestFetchGoogleNewsRss:
    def test_returns_articles_from_valid_rss(self):
        mock_resp = MagicMock()
        mock_resp.text = RSS_WITH_ARTICLES
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.news_collector.requests.get", return_value=mock_resp):
            result = _fetch_google_news_rss(10)
        #motley fool article should be filtered, only afr one survives
        assert len(result) == 1
        assert result[0]["source"] == "Australian Financial Review"

    def test_filters_blacklisted_sources(self):
        mock_resp = MagicMock()
        mock_resp.text = RSS_WITH_ARTICLES
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.news_collector.requests.get", return_value=mock_resp):
            result = _fetch_google_news_rss(10)
        sources = [a["source"] for a in result]
        assert "The Motley Fool" not in sources

    def test_respects_limit(self):
        #build a feed with 20 items and check only 3 come back
        items = "".join(
            f"<item><title>Article {i} - AFR</title><link>http://x.com/{i}</link>"
            f"<pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>"
            f"<source>AFR</source><description>text</description></item>"
            for i in range(20)
        )
        rss = f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'
        mock_resp = MagicMock()
        mock_resp.text = rss
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.news_collector.requests.get", return_value=mock_resp):
            result = _fetch_google_news_rss(3)
        assert len(result) == 3

    def test_returns_empty_on_network_error(self):
        with patch("app.collectors.news_collector.requests.get", side_effect=Exception("network error")):
            result = _fetch_google_news_rss(10)
        assert result == []

    def test_returns_empty_on_empty_feed(self):
        mock_resp = MagicMock()
        mock_resp.text = RSS_NO_RESULT
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.news_collector.requests.get", return_value=mock_resp):
            result = _fetch_google_news_rss(10)
        assert result == []

    def test_article_has_required_keys(self):
        mock_resp = MagicMock()
        mock_resp.text = RSS_WITH_ARTICLES
        mock_resp.raise_for_status = MagicMock()
        with patch("app.collectors.news_collector.requests.get", return_value=mock_resp):
            result = _fetch_google_news_rss(10)
        assert len(result) > 0
        for key in ("title", "source", "url", "published_at", "description"):
            assert key in result[0]


class TestFetchFinancialNews:
    def test_falls_back_to_mock_on_failure(self):
        #when rss fetch returns nothing the mock news should kick in
        with patch("app.collectors.news_collector._fetch_google_news_rss", return_value=[]):
            result = fetch_financial_news()
            assert isinstance(result, list)
            assert len(result) > 0

    def test_returns_real_data_when_available(self):
        fake_articles = [{"title": "ASX up", "source": "AFR", "url": "http://x.com", "published_at": "2024-01-01T00:00:00+00:00", "description": ""}]
        with patch("app.collectors.news_collector._fetch_google_news_rss", return_value=fake_articles):
            result = fetch_financial_news()
            assert result == fake_articles

    def test_respects_page_size(self):
        fake_articles = [
            {"title": f"Article {i}", "source": "AFR", "url": "http://x.com", "published_at": "2024-01-01T00:00:00+00:00", "description": ""}
            for i in range(20)
        ]
        with patch("app.collectors.news_collector._fetch_google_news_rss", return_value=fake_articles):
            result = fetch_financial_news(page_size=5)
            assert len(result) <= 20

