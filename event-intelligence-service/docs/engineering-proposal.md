# Engineering Proposal — Event Intelligence Service

---

## Overview

The Event Intelligence Service is a RESTful API that collects, standardises, and analyses
Australian Securities Exchange (ASX) stock data and financial news.
It exposes stock quotes, OHLCV history, keyword-based sentiment analysis, and
ADAGE 3.0-formatted event datasets to downstream consumers.

---

## Technology Stack

| Layer | Technology | Role |
|---|---|---|
| **Container** | Docker (Python 3.11-slim) | Portable deployment, port mapping 8000:8000 |
| **ASGI Server** | Uvicorn 0.27 | Production-grade async HTTP server |
| **Web Framework** | FastAPI 0.109 | Route handling, validation, OpenAPI docs |
| **Data Validation** | Pydantic 2.5 | ADAGE 3.0 schema enforcement |
| **Stock Data** | Yahoo Finance Chart API v8 (unofficial) | Real-time quotes and OHLCV history |
| **News Data** | Google News RSS (AU locale) | Australian financial news feed |
| **Sentiment Engine** | Custom keyword lexicon (Python) | Positive/negative/neutral classification |
| **Storage** | Local JSON files (filesystem) | Raw and standardised ADAGE event datasets |
| **Testing** | Pytest + pytest-cov + HTTPX | Unit and integration tests |

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph Client["Client Layer"]
        B([Browser / API Consumer])
    end

    subgraph Docker["Docker Container  :8000"]
        UV[Uvicorn ASGI Server]
        subgraph FastAPI["FastAPI Application"]
            MW[CORSMiddleware]
            CR[CollectRoutes\n/collect/*]
            AR[AnalysisRoutes\n/api/*]
        end
    end

    subgraph Services["Service Layer"]
        SS[StorageService\nJSON file I/O]
        AS[AnalysisService\nKeyword Sentiment]
    end

    subgraph Collectors["Collector Layer"]
        SC[StockCollector\nYahoo Finance v8]
        NC[NewsCollector\nGoogle News RSS]
    end

    subgraph FileSystem["File System  backend/data/"]
        RAW["data/raw/\n  stocks/*.json\n  news/*.json"]
        STD["data/standardised/\n  combined_events.json\n  history_events.json"]
    end

    subgraph External["External APIs"]
        YF[(Yahoo Finance\nquery1 + query2)]
        GN[(Google News\nRSS AU locale)]
    end

    B -->|HTTP| UV
    UV --> MW --> CR & AR
    CR & AR --> SS & AS
    CR & AR --> SC & NC
    SC -->|HTTPS GET| YF
    NC -->|HTTPS GET| GN
    SS -->|write| RAW
    SS -->|read/write| STD
```

---

## Sequence Diagram 1 — Full Data Collection Pipeline (`POST /collect/pipeline`)

This diagram shows the complete end-to-end flow when a client triggers the data ingestion pipeline.
It covers every layer of the stack: Docker networking, Uvicorn, FastAPI routing, collector HTTP calls
to external APIs, sentiment analysis, file system writes, and the final JSON response.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client<br/>(Browser / curl)
    participant Docker as Docker<br/>:8000 → :8000
    participant UV as Uvicorn<br/>ASGI Server
    participant MW as CORS<br/>Middleware
    participant CR as CollectRoutes<br/>POST /collect/pipeline
    participant SC as StockCollector
    participant NC as NewsCollector
    participant AS as AnalysisService
    participant SS as StorageService
    participant YF as Yahoo Finance<br/>Chart API v8
    participant GN as Google News<br/>RSS (AU)
    participant FS as File System<br/>backend/data/

    %% ── Incoming request ──────────────────────────────────────────
    Client  ->>+ Docker : HTTP POST /collect/pipeline?tickers=BHP,CBA,NAB
    Docker  ->>+ UV     : forward TCP :8000
    UV      ->>+ MW     : ASGI scope + receive
    MW      -->> MW     : add CORS headers
    MW      ->>+ CR     : dispatch to router

    %% ── Step 1: Fetch stock quotes ────────────────────────────────
    note over CR: Normalise tickers → BHP.AX, CBA.AX, NAB.AX
    CR      ->>+ SC     : fetch_multiple_stocks(["BHP","CBA","NAB"])

    loop For each ticker (with 0.5 s delay)
        SC  ->>+ YF     : HTTPS GET query1.finance.yahoo.com<br/>/v8/finance/chart/BHP.AX<br/>?range=5d&interval=1d
        alt HTTP 200 — chart data returned
            YF  -->> SC : JSON { chart.result[0]: meta, timestamps, indicators }
            SC  -->> SC : extract close[], open[], volume[]<br/>compute change_percent
        else HTTP error or empty result
            YF  -->> SC : 4xx / 5xx / empty
            SC  ->>+ YF : retry → query2.finance.yahoo.com (fallback)
            alt Fallback succeeds
                YF  -->>- SC : JSON data
            else Both fail + USE_MOCK_STOCKS=true
                SC  -->> SC : _mock_stock_data(symbol)<br/>return hardcoded price
            end
        end
    end
    SC      -->>- CR    : list[StockQuote dict] × 3

    %% ── Step 2: Save raw stock JSON ──────────────────────────────
    CR      ->>+ SS     : save_raw(stocks, "stocks", "stocks_<ts>.json")
    SS      ->>+ FS     : mkdir -p data/raw/stocks/<br/>write JSON file
    FS      -->>- SS    : OK
    SS      -->>- CR    : file path

    %% ── Step 3: Fetch financial news ─────────────────────────────
    CR      ->>+ NC     : fetch_financial_news(page_size=500)

    loop Up to 5 RSS query strings (dedup by URL)
        NC  ->>+ GN     : HTTPS GET news.google.com/rss/search<br/>?q=ASX+Australian+stock+market&hl=en-AU&gl=AU
        alt RSS feed returns XML
            GN  -->> NC : XML <rss><channel><item>...</item></channel></rss>
            NC  -->> NC : ET.fromstring → parse <item> elements<br/>filter blacklisted sources<br/>filter clickbait titles<br/>deduplicate by URL<br/>_strip_html(description)<br/>_parse_rss_date → ISO 8601
        else All feeds fail
            GN  -->>- NC : connection error / timeout
            NC  -->> NC  : _mock_news() → 2 hardcoded articles
        end
    end
    NC      -->>- CR    : list[Article dict] (title, source, url,<br/>published_at, description)

    %% ── Step 4: Save raw news JSON ───────────────────────────────
    CR      ->>+ SS     : save_raw(news, "news", "news_<ts>.json")
    SS      ->>+ FS     : write data/raw/news/news_<ts>.json
    FS      -->>- SS    : OK
    SS      -->>- CR    : file path

    %% ── Step 5: Sentiment analysis per article ───────────────────
    loop For each Article
        CR  ->>+ AS     : analyse_sentiment(title + " " + description)
        AS  -->> AS     : tokenise → word set<br/>intersect with POSITIVE_WORDS / NEGATIVE_WORDS<br/>score = min(0.5 + |pos-neg|×0.15, 1.0)
        AS  -->>- CR    : ("positive"|"negative"|"neutral", impact_score)

        CR  ->>+ AS     : extract_related_stocks(text, ["BHP","CBA","NAB"])
        AS  -->> AS     : text.upper() substring match<br/>append ".AX" suffix
        AS  -->>- CR    : ["BHP.AX"] or []
    end

    %% ── Step 6: Assemble ADAGE EventDataset ─────────────────────
    note over CR: Build EventDataset {<br/>  data_source: "event_intelligence",<br/>  dataset_type: "Mixed",<br/>  dataset_id: "s3://event-intelligence/combined_events.json",<br/>  time_object: { timestamp: now_utc, timezone: "UTC" },<br/>  events: [<br/>    Stock quote × 3,<br/>    Stock news × N (each with sentiment + related_stock)<br/>  ]<br/>}

    %% ── Step 7: Save standardised dataset ───────────────────────
    CR      ->>+ SS     : save_standardised(dataset, "combined_events.json")
    SS      ->>+ FS     : write data/standardised/combined_events.json<br/>(overwrites previous)
    FS      -->>- SS    : OK
    SS      -->>- CR    : file path

    %% ── Step 8: Return response ──────────────────────────────────
    CR      -->>- MW    : 200 { events_count: N+3, stocks: 3, news: N }
    MW      -->>- UV    : add Access-Control-Allow-Origin: *
    UV      -->>- Docker: HTTP 200 JSON response
    Docker  -->>- Client: HTTP 200 { "events_count": 53, "stocks": 3, "news": 50 }
```

---

## Sequence Diagram 2 — End-to-End Sentiment Query (`GET /api/sentiment?stock=BHP`)

This diagram shows the complete request lifecycle for the primary read-path use case.
It demonstrates the cache-first strategy, the full stack traversal on a cache miss,
and how stock price data is combined with analysed news to produce a composite sentiment response.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client<br/>(Browser / curl)
    participant Docker as Docker<br/>:8000 → :8000
    participant UV as Uvicorn<br/>ASGI Server
    participant MW as CORS<br/>Middleware
    participant AR as AnalysisRoutes<br/>GET /api/sentiment
    participant SS as StorageService
    participant SC as StockCollector
    participant NC as NewsCollector
    participant AS as AnalysisService
    participant FS as File System<br/>backend/data/
    participant YF as Yahoo Finance<br/>Chart API v8
    participant GN as Google News<br/>RSS (AU)

    %% ── Incoming request ──────────────────────────────────────────
    Client  ->>+ Docker : HTTP GET /api/sentiment?stock=BHP
    Docker  ->>+ UV     : forward TCP :8000
    UV      ->>+ MW     : ASGI scope + receive
    MW      -->> MW     : validate Origin, add CORS headers
    MW      ->>+ AR     : dispatch to AnalysisRoutes

    AR      -->> AR     : _normalise("BHP") → "BHP.AX"

    %% ── Branch A: Cache hit ───────────────────────────────────────
    AR      ->>+ SS     : load_standardised("combined_events.json")
    SS      ->>+ FS     : stat + open data/standardised/combined_events.json

    alt FILE EXISTS (cache hit)
        FS  -->>- SS    : JSON bytes
        SS  -->> SS     : json.load() → EventDataset dict
        SS  -->>- AR    : EventDataset { data_source, events: [...] }

        AR  -->> AR     : filter events where<br/>event_type == "Stock quote"<br/>AND attribute.ticker == "BHP.AX"
        note right of AR: stock_data = events[0].attribute<br/>{ Quote Price, Previous Close,<br/>  Open, Volume, change_percent }

        AR  -->> AR     : filter events where<br/>event_type == "Stock news"<br/>AND attribute.related_stock == "BHP.AX"

        alt No ticker-specific news found
            AR -->> AR  : fallback → take up to 5 general news events<br/>(related_stock == null)
        end

        AR  -->> AR     : _aggregate_sentiment(news_events)<br/>count pos / neg / neutral<br/>return majority label (tie → "neutral")

        AR  -->>- MW    : 200 {<br/>  stock: "BHP.AX",<br/>  cached: true,<br/>  stock_data: { Quote Price: 45.20, ... },<br/>  overall_sentiment: "positive",<br/>  related_news: [ {title, sentiment, impact_score} × 10 ]<br/>}

    else FILE NOT FOUND (cache miss — live fetch)
        FS  -->>- SS    : FileNotFoundError
        SS  -->>- AR    : None

        %% ── Live stock quote ────────────────────────────────────
        AR  ->>+ SC     : fetch_stock_data("BHP.AX")
        SC  ->>+ YF     : HTTPS GET query1.finance.yahoo.com<br/>/v8/finance/chart/BHP.AX?range=5d&interval=1d
        alt Yahoo returns data
            YF  -->> SC : JSON chart result
            SC  -->> SC : extract regularMarketPrice,<br/>previousClose, open, volume,<br/>regularMarketChangePercent
            SC  -->>- AR: StockQuote dict { ticker, Quote Price, ... }
        else Yahoo fails
            YF  -->>- SC: error
            SC  -->> SC : USE_MOCK_STOCKS=true → _mock_stock_data("BHP.AX")
            SC  -->>- AR: mock StockQuote dict
        end

        %% ── Live news fetch + sentiment ─────────────────────────
        AR  ->>+ NC     : fetch_financial_news()
        NC  ->>+ GN     : HTTPS GET news.google.com/rss/search?q=ASX+...&gl=AU
        GN  -->>- NC    : XML feed
        NC  -->> NC     : parse → filter → deduplicate
        NC  -->>- AR    : list[Article] (up to 500)

        loop For each of first 10 articles
            AR  ->>+ AS : analyse_sentiment(title + description)
            AS  -->>- AR: (sentiment, impact_score)
            AR  ->>+ AS : extract_related_stocks(text, ["BHP"])
            AS  -->>- AR: ["BHP.AX"] or []
        end

        AR  -->> AR     : _aggregate_sentiment(news_events)

        AR  -->>- MW    : 200 {<br/>  stock: "BHP.AX",<br/>  cached: false,<br/>  stock_data: { Quote Price: 45.20, ... },<br/>  overall_sentiment: "negative",<br/>  related_news: [ {title, sentiment, impact_score} × 10 ]<br/>}
    end

    %% ── Response path ─────────────────────────────────────────────
    MW      -->>- UV    : HTTP 200 + Access-Control-Allow-Origin: *
    UV      -->>- Docker: serialise JSON response body
    Docker  -->>- Client: HTTP 200 JSON<br/>Content-Type: application/json
```

---

## Key Design Decisions

### Cache-First Read Strategy
All `GET /api/*` endpoints attempt to load from the pre-computed standardised JSON file
before making any external API calls. This minimises latency on repeat queries and
avoids hitting Yahoo Finance or Google News rate limits during normal read traffic.
The trade-off is that cached data may be stale until the next `POST /collect/pipeline` run.

### Dual-URL Yahoo Finance Fallback
`query1.finance.yahoo.com` and `query2.finance.yahoo.com` are tried in sequence.
If both fail (e.g. in CI or blocked networks), the `USE_MOCK_STOCKS` environment variable
enables deterministic mock prices for all 10 pre-defined ASX tickers.

### ADAGE 3.0 as the Canonical Output Format
All data — regardless of source — is transformed into the ADAGE `EventDataset` structure
before being persisted or returned. This ensures a single consistent schema for downstream
consumers and satisfies the project specification requirement.

### Stateless Service Design
The service itself holds no in-memory state between requests.
All persistence is delegated to the file system. This means the Docker container can be
restarted without data loss (provided the `data/` volume is mounted or the files survive),
and horizontal scaling is straightforward (though concurrent writes are not yet safe).
