# Assumptions — Event Intelligence Service

> This page documents every assumption made during the design and implementation of the service,
> arising from ambiguities in the ADAGE 3.0 specification and the broader project brief.
> Assumptions are grouped by concern area and numbered for traceability.

---

## A. Market Scope & Ticker Handling

**A1 — ASX-only coverage**
The service is assumed to cover only Australian Securities Exchange (ASX) equities.
No US, UK, or other international exchanges are in scope for this iteration.

**A2 — Automatic `.AX` suffix normalisation**
Any ticker submitted without a `.AX` suffix (e.g. `BHP`) is automatically treated as an ASX ticker
and normalised to `BHP.AX` before any API call. Tickers already carrying `.AX` are passed through unchanged.
It is assumed all client-supplied tickers refer to ASX-listed instruments.

**A3 — Default ticker set**
When no tickers are specified in a collect request, the service defaults to the five largest ASX stocks
by market capitalisation at the time of implementation: `BHP`, `CBA`, `NAB`, `WBC`, `ANZ`.
This set is assumed to be representative enough for demonstration purposes.

**A4 — Single exchange per request**
It is assumed that a single pipeline run targets one exchange only (ASX).
Mixed exchange requests (e.g. BHP.AX + AAPL) are not validated and may produce undefined behaviour.

---

## B. External Data Sources

**B1 — Yahoo Finance unofficial API**
Stock price data is sourced from Yahoo Finance's Chart API v8 (`query1.finance.yahoo.com`),
which is an **unofficial, unauthenticated endpoint** with no SLA or rate-limit guarantee.
It is assumed this endpoint remains stable enough for development and demonstration use.
A `query2` fallback URL is attempted automatically on failure.

**B2 — Google News RSS as news source**
Financial news is fetched from Google News RSS feeds (no API key required).
Despite `NEWS_API_KEY` appearing in `.env.example`, `newsapi.org` is **not** used in the current implementation.
It is assumed Google News RSS provides sufficiently broad Australian financial market coverage
for the purposes of this service.

**B3 — Google News RSS item limit (~100 per feed)**
Google News RSS typically returns at most ~100 articles per search query.
To work around this cap, the service rotates across 5 pre-defined query strings and deduplicates by URL.
It is assumed these 5 queries collectively provide adequate coverage of the ASX news landscape.

**B4 — News article URLs are Google redirect URLs**
Google News RSS wraps article links inside a Google redirect URL rather than linking directly to the
original publisher. These redirect URLs are stored as-is. It is assumed consumers of the API can
follow these redirects to reach the source article.

**B5 — 0.5s inter-request delay is sufficient**
A 0.5-second sleep between consecutive Yahoo Finance requests is assumed to be adequate to avoid
triggering rate-limiting or IP bans during normal operation.

---

## C. Data Storage & Persistence

**C1 — File-based storage (no database)**
The ADAGE 3.0 specification does not mandate a particular persistence mechanism.
It is assumed that flat JSON files stored on the local filesystem are an acceptable storage layer
for this stage of development, avoiding the complexity of provisioning a database.

**C2 — Standardised files are overwritten on each pipeline run**
Each invocation of `POST /collect/pipeline` or `POST /collect/history` **overwrites**
`combined_events.json` and `history_events.json` respectively.
It is assumed that the most-recent dataset is always the canonical dataset,
and that no versioning or append-style accumulation is required.

**C3 — No concurrent write safety**
The file I/O layer provides no locking mechanism.
It is assumed that pipeline collection endpoints are not called concurrently.
Simultaneous writes to the same standardised file could produce corrupted JSON.

**C4 — `dataset_id` as S3 URI placeholder**
The ADAGE `dataset_id` field is populated with a placeholder S3 path
(e.g. `s3://event-intelligence/combined_events.json`) even though no S3 bucket exists.
It is assumed this satisfies the schema requirement and can be replaced with a real URI
when cloud storage is provisioned.

**C5 — Raw files are append-only by timestamp**
Raw data files (under `data/raw/`) are written with a UTC timestamp in the filename
(e.g. `stocks_20260320_120000.json`). They are never cleaned up or rotated.
It is assumed storage space is not a constraint during development.

---

## D. Cache Strategy

**D1 — Cache-first, stale-acceptable**
All `GET /api/*` endpoints read from the standardised JSON cache first.
If a cache file exists, it is returned **regardless of its age**.
No TTL or staleness check is implemented.
It is assumed that clients who require fresh data will trigger a `POST /collect/*` endpoint first.

**D2 — Cache miss falls back to live fetch**
If no cache file exists, endpoints fall back to fetching live data from Yahoo Finance or Google News RSS.
It is assumed live fallback is acceptable even though it adds latency and may produce slightly different
results compared to a pipeline-generated cache.

**D3 — `GET /api/events` requires prior pipeline run**
`GET /api/events` returns a `404` if `combined_events.json` does not exist.
It is assumed that operators will run `POST /collect/pipeline` at least once before querying this endpoint.

---

## E. Sentiment Analysis

**E1 — Keyword-based sentiment is sufficient**
Sentiment is determined by counting occurrences of pre-defined positive and negative word sets
against the tokenised article text (title + description).
It is assumed that a lexicon-based approach is adequate for a first iteration and that
the costs and complexity of a production NLP/ML model are out of scope.

**E2 — Sentiment applies to article text, not price movement**
The sentiment score reflects the textual tone of a news article, not an independent signal
derived from price data. It is assumed these are treated as distinct data points by consumers.

**E3 — Impact score formula**
Impact score is calculated as `min(0.5 + (|pos - neg|) × 0.15, 1.0)`, floored at `0.0`.
A neutral article scores exactly `0.5`.
It is assumed this linear scaling adequately represents the "strength" of a sentiment signal
for the purposes of this service.

**E4 — Majority-vote overall sentiment**
When aggregating multiple news articles into a single `overall_sentiment` for a stock,
the sentiment with the most votes wins. Ties resolve to `"neutral"`.
It is assumed this is an acceptable simplification of sentiment aggregation.

**E5 — Sentiment is computed at ingest time**
Sentiment is analysed when articles are collected (pipeline or live fetch) and stored in the event.
It is assumed re-analysis is not required after storage; the stored sentiment is the authoritative value.

---

## F. Related Stock Extraction

**F1 — Only explicitly known tickers are matched**
`extract_related_stocks` performs a case-insensitive substring search against a list of tickers
supplied at call time. It cannot discover tickers that are not already known to the caller.
It is assumed the relevant ticker universe is always known at collection time.

**F2 — Only the first matched ticker is stored per article**
Even if multiple known tickers are mentioned in an article, only `related[0]` is stored in the event
attribute. It is assumed articles are primarily "about" one stock, and that multi-stock association
is out of scope for this iteration.

**F3 — Short ticker names may produce false positives**
Very short ticker codes (e.g. `up` if used as a ticker) could match common English words.
It is assumed the default ASX ticker set (BHP, CBA, NAB, WBC, ANZ, etc.) is sufficiently distinct
from common English vocabulary to avoid significant false positives.

---

## G. Technical Indicators

**G1 — Trading days per year = 252**
Annualised volatility is computed as `daily_std × sqrt(252)`.
It is assumed the ASX has approximately 252 trading days per year, consistent with international convention.

**G2 — MA5 and MA20 use available data when fewer than 5 or 20 days exist**
If fewer than 5 (or 20) data points are available, MA5 (or MA20) is computed over all available points.
It is assumed a partial moving average is more useful than returning `None` in these edge cases.

**G3 — Adjusted Close falls back to Close**
If Yahoo Finance does not return adjusted close values, the regular close price is used as `Adj Close`.
It is assumed the difference is negligible for the short periods queried (up to 1 year).

**G4 — 52-week high/low sourced from Yahoo `meta`**
`week52_high` and `week52_low` are taken directly from Yahoo Finance's `meta.fiftyTwoWeekHigh`
and `meta.fiftyTwoWeekLow` rather than being computed from OHLC history.
It is assumed Yahoo's pre-computed values are accurate and sufficient.

---

## H. ADAGE 3.0 Format Interpretation

**H1 — `time_object.timestamp` uses `"YYYY-MM-DD HH:MM:SS"` format**
The ADAGE specification allows ISO 8601 timestamps.
The implementation uses `"%Y-%m-%d %H:%M:%S"` (space-separated, no `T`, no `Z`) for collection timestamps.
Article publication times use full ISO 8601 with timezone offset (as returned by the RSS parser).
It is assumed both formats are ADAGE-compliant.

**H2 — All service-generated timestamps are UTC**
All `TimeObject.timezone` values are hardcoded to `"UTC"`.
It is assumed the service operates in UTC and that all downstream consumers interpret timestamps accordingly.

**H3 — News event `duration` is fixed at 1 hour**
All `Stock news` events are assigned `"duration": 1, "duration_unit": "hour"`.
It is assumed a news article's market relevance window is approximately 1 hour,
consistent with high-frequency financial event modelling conventions.

**H4 — `attribute` is a free-form dict, not a typed schema**
The ADAGE `Event.attribute` field is treated as an open dictionary.
Different `event_type` values (`Stock quote`, `Stock news`, `Stock ohlc`, `Stock analysis`)
carry different keys. It is assumed consumers are aware of the schema per `event_type`.

**H5 — `data_source` at dataset level vs event level**
The `EventDataset.data_source` is set to `"event_intelligence"` (this service).
Individual events also carry a `data_source` key inside `attribute` pointing to the upstream origin
(e.g. `"yahoo_finance"`, `"google_news_rss"`). It is assumed both levels of attribution are useful
and non-contradictory.

---

## I. API Design & Security

**I1 — No authentication or authorisation**
The API is fully public with no API keys, JWT tokens, or session management.
It is assumed the service runs in a controlled/private network environment (e.g. Docker on localhost)
and that authentication is out of scope for this deliverable.

**I2 — CORS is fully open**
`CORSMiddleware` is configured with `allow_origins=["*"]`.
It is assumed any frontend (including local dev servers) needs unrestricted access.

**I3 — Mock data enabled by default**
`USE_MOCK_STOCKS` defaults to `"true"` when not set in the environment.
It is assumed this is the correct default for development and CI environments where Yahoo Finance
may be unreachable, and that production deployments will explicitly set it to `"false"`.

**I4 — Allowed history periods are a fixed enum**
`POST /collect/history` validates `period` against `{"1mo", "3mo", "6mo", "1y"}`.
It is assumed these four periods cover all use cases required by the specification.
Any other value (e.g. `"2y"`) is rejected with HTTP 400.

**I5 — `GET /api/news` with `ticker` filter includes unrelated articles to fill quota**
When filtering news by ticker, if fewer matched articles exist than the requested `limit`,
the response is padded with general (unrelated) news articles.
It is assumed general market news is relevant context even when it does not explicitly name the ticker.
