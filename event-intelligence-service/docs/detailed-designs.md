# Detailed Designs — Event Intelligence Service

> All diagrams use [Mermaid](https://mermaid.js.org/) syntax.
> Paste into any Confluence page that has the Mermaid macro, or preview at https://mermaid.live.

---

## 1. ER Diagram — Data Model & File Storage

The system uses **file-based JSON storage** (no relational database).
This diagram shows the logical entity relationships and the on-disk layout.

```mermaid
erDiagram
    EventDataset {
        string data_source
        string dataset_type
        string dataset_id
        TimeObject time_object
    }
    Event {
        string event_type
        dict   attribute
        TimeObject time_object
    }
    TimeObject {
        string   timestamp
        int      duration
        string   duration_unit
        string   timezone
    }
    RawNewsFile {
        string filename
        string directory
        list   articles
    }
    RawStocksFile {
        string filename
        string directory
        list   quotes
    }
    Article {
        string title
        string source
        string url
        string published_at
        string description
    }
    StockQuote {
        string ticker
        float  quote_price
        float  previous_close
        float  open
        int    volume
        float  change_percent
    }

    EventDataset ||--o{ Event          : "contains"
    EventDataset ||--|| TimeObject     : "has"
    Event        ||--|| TimeObject     : "has"

    RawNewsFile  ||--o{ Article        : "stores"
    RawStocksFile||--o{ StockQuote     : "stores"

    EventDataset }o--|| RawNewsFile    : "derived from"
    EventDataset }o--|| RawStocksFile  : "derived from"
```

### Standardised File Layout

```mermaid
erDiagram
    STANDARDISED_DIR {
        file combined_events_json
        file history_events_json
    }
    RAW_DIR {
        dir  news
        dir  stocks
    }
    combined_events_json ||--o{ EventDataset : "serialises"
    history_events_json  ||--o{ EventDataset : "serialises"
    RAW_DIR              ||--o{ RawNewsFile  : "stores"
    RAW_DIR              ||--o{ RawStocksFile: "stores"
```

---

## 2. UML Class Diagram

```mermaid
classDiagram
    %% ─── Data Models (Pydantic) ───
    class TimeObject {
        +str timestamp
        +Optional~int~ duration
        +Optional~str~ duration_unit
        +str timezone
    }

    class Event {
        +TimeObject time_object
        +str event_type
        +dict attribute
    }

    class EventDataset {
        +str data_source
        +str dataset_type
        +str dataset_id
        +TimeObject time_object
        +list~Event~ events
    }

    EventDataset "1" *-- "1" TimeObject : dataset time
    EventDataset "1" *-- "0..*" Event   : events
    Event        "1" *-- "1" TimeObject : event time

    %% ─── Storage Service ───
    class StorageService {
        -str BASE_DIR
        -str RAW_DIR
        -str STANDARDISED_DIR
        +save_raw(data, subdir, filename) str
        +save_standardised(data, filename) str
        +load_standardised(filename) dict|None
    }

    %% ─── Analysis Service ───
    class AnalysisService {
        -set POSITIVE_WORDS
        -set NEGATIVE_WORDS
        +analyse_sentiment(text) tuple~str_float~
        +extract_related_stocks(text, known_tickers) list~str~
    }

    %% ─── Stock Collector ───
    class StockCollector {
        -str YAHOO_QUERY1_URL
        -str YAHOO_QUERY2_URL
        -bool USE_MOCK_STOCKS
        +fetch_stock_data(ticker) Optional~dict~
        +fetch_multiple_stocks(tickers) list~dict~
        +fetch_stock_history(ticker, period) Optional~dict~
        -_normalise_symbol(ticker) str
        -_fetch_yahoo_chart(symbol) Optional~dict~
        -_mock_stock_data(symbol) dict
        -_compute_indicators(closes, meta) dict
    }

    %% ─── News Collector ───
    class NewsCollector {
        -list RSS_QUERIES
        -list BLACKLISTED_SOURCES
        +fetch_financial_news(page_size) list~dict~
        -_fetch_google_news_rss(limit) list~dict~
        -_fetch_single_rss(url, remaining, seen_urls) list~dict~
        -_is_blacklisted(source) bool
        -_is_farm_content(title) bool
        -_parse_rss_date(date_str) str
        -_extract_source_name(item, title) str
        -_strip_html(text) str
        -_mock_news() list~dict~
    }

    %% ─── Route Handlers ───
    class CollectRoutes {
        <<FastAPI Router>>
        +POST /collect/stocks(tickers)
        +POST /collect/news()
        +POST /collect/history(tickers, period)
        +POST /collect/pipeline(tickers)
    }

    class AnalysisRoutes {
        <<FastAPI Router>>
        +GET /api/news(ticker, limit)
        +GET /api/stock(ticker, include_ohlc)
        +GET /api/analysis(stock, period)
        +GET /api/sentiment(stock)
        +GET /api/events()
        -_normalise(ticker) str
        -_now_iso() str
        -_aggregate_sentiment(news_events) str
    }

    class FastAPIApp {
        <<FastAPI>>
        +title: "Event Intelligence API"
        +version: "0.1.0"
        +CORSMiddleware
        +GET /
    }

    %% ─── Dependencies ───
    FastAPIApp     --> CollectRoutes  : mounts
    FastAPIApp     --> AnalysisRoutes : mounts

    CollectRoutes  --> StockCollector  : uses
    CollectRoutes  --> NewsCollector   : uses
    CollectRoutes  --> StorageService  : uses
    CollectRoutes  --> AnalysisService : uses
    CollectRoutes  ..> EventDataset    : creates

    AnalysisRoutes --> StockCollector  : uses
    AnalysisRoutes --> NewsCollector   : uses
    AnalysisRoutes --> StorageService  : uses
    AnalysisRoutes --> AnalysisService : uses
    AnalysisRoutes ..> EventDataset    : reads
```

---

## 3. Sequence Diagrams

### 3.1 POST `/collect/pipeline` — Full Data Collection Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant CR  as CollectRoutes
    participant SC  as StockCollector
    participant NC  as NewsCollector
    participant AS  as AnalysisService
    participant SS  as StorageService
    participant YF  as Yahoo Finance API
    participant GN  as Google News RSS

    Client ->>+ CR: POST /collect/pipeline?tickers=BHP,CBA,...

    %% ── Step 1: Fetch stocks ──
    CR ->>+ SC: fetch_multiple_stocks(tickers)
    loop For each ticker (0.5s delay)
        SC ->>+ YF: GET chart/v8/{symbol}?interval=1d&range=5d
        alt Yahoo returns 200
            YF -->> SC: JSON (meta + quotes)
        else Yahoo fails
            SC -->> SC: _mock_stock_data(symbol)
        end
    end
    SC -->>- CR: list[StockQuote dict]

    %% ── Step 2: Save raw stocks ──
    CR ->>+ SS: save_raw(stocks, "stocks", filename)
    SS -->>- CR: file path

    %% ── Step 3: Fetch news ──
    CR ->>+ NC: fetch_financial_news()
    loop Up to 5 RSS queries
        NC ->>+ GN: GET /rss/search?q=...
        alt RSS returns articles
            GN -->> NC: XML feed
            NC -->> NC: _parse_rss_date, _strip_html, dedup
        else All feeds fail
            NC -->> NC: _mock_news()
        end
    end
    NC -->>- CR: list[Article dict]

    %% ── Step 4: Save raw news ──
    CR ->>+ SS: save_raw(news, "news", filename)
    SS -->>- CR: file path

    %% ── Step 5: Sentiment analysis ──
    loop For each article
        CR ->>+ AS: analyse_sentiment(title + description)
        AS -->>- CR: (sentiment, impact_score)
        CR ->>+ AS: extract_related_stocks(text, known_tickers)
        AS -->>- CR: [related_ticker, ...]
    end

    %% ── Step 6: Assemble ADAGE EventDataset ──
    CR -->> CR: Build EventDataset{<br/>  events: [Stock quote × N] + [Stock news × M]<br/>}

    %% ── Step 7: Save standardised ──
    CR ->>+ SS: save_standardised(dataset, "combined_events.json")
    SS -->>- CR: file path

    CR -->>- Client: 200 { dataset_id, event_count, stock_count, news_count }
```

---

### 3.2 POST `/collect/history` — OHLCV History Collection

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant CR  as CollectRoutes
    participant SC  as StockCollector
    participant SS  as StorageService
    participant YF  as Yahoo Finance API

    Client ->>+ CR: POST /collect/history?tickers=BHP&period=1mo

    loop For each ticker
        CR ->>+ SC: fetch_stock_history(ticker, period)
        SC -->> SC: _normalise_symbol(ticker)  → "BHP.AX"
        SC ->>+ YF: GET chart/v8/BHP.AX?interval=1d&range=1mo
        alt Yahoo returns data
            YF -->> SC: timestamps[] + ohlcv[] + meta{}
            SC -->> SC: _compute_indicators(closes, meta)<br/>→ MA5, MA20, volatility, 52w-high/low
        else Yahoo fails
            YF -->> SC: error
            SC -->> SC: return None (skip ticker)
        end
        SC -->>- CR: { quote, ohlc_series[], indicators{}, period }
    end

    CR -->> CR: Build EventDataset{<br/>  events: [Stock ohlc × days × tickers]<br/>}
    CR ->>+ SS: save_standardised(dataset, "history_events.json")
    SS -->>- CR: file path
    CR -->>- Client: 200 { dataset_id, ticker_count, event_count }
```

---

### 3.3 GET `/api/news` — News Query with Cache-First Strategy

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant AR  as AnalysisRoutes
    participant SS  as StorageService
    participant NC  as NewsCollector
    participant AS  as AnalysisService
    participant GN  as Google News RSS
    participant FS  as File System

    Client ->>+ AR: GET /api/news?ticker=BHP&limit=20

    %% ── Cache check ──
    AR ->>+ SS: load_standardised("combined_events.json")
    SS ->>+ FS: read file
    alt File exists
        FS -->> SS: JSON content
        SS -->>- AR: EventDataset dict
        AR -->> AR: Filter events where<br/>event_type == "Stock news"<br/>AND ticker in attribute.related_stock
        AR -->>- Client: 200 { events: [...], total: N, source: "cache" }
    else File not found
        SS -->>- AR: None
        AR ->>+ NC: fetch_financial_news()
        NC ->>+ GN: RSS feeds
        GN -->> NC: articles
        NC -->>- AR: list[Article]
        loop For each article
            AR ->>+ AS: analyse_sentiment(text)
            AS -->>- AR: (sentiment, impact_score)
            AR ->>+ AS: extract_related_stocks(text, tickers)
            AS -->>- AR: [related, ...]
        end
        AR -->> AR: Build & filter ADAGE events
        AR -->>- Client: 200 { events: [...], total: N, source: "live" }
    end
```

---

### 3.4 GET `/api/stock` — Stock Quote (with optional OHLC)

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant AR  as AnalysisRoutes
    participant SS  as StorageService
    participant SC  as StockCollector
    participant YF  as Yahoo Finance API

    Client ->>+ AR: GET /api/stock?ticker=CBA&include_ohlc=true

    AR -->> AR: _normalise("CBA") → "CBA.AX"

    %% ── Cache check ──
    AR ->>+ SS: load_standardised("combined_events.json")
    alt Cache hit — ticker found
        SS -->> AR: EventDataset
        AR -->> AR: Extract "Stock quote" event for CBA.AX
        note over AR: include_ohlc=true → also load history cache
        AR ->>+ SS: load_standardised("history_events.json")
        alt History cache exists
            SS -->> AR: history EventDataset
        else No history cache
            SS -->> AR: None
            AR ->>+ SC: fetch_stock_history("CBA.AX", "1mo")
            SC ->>+ YF: GET chart/v8/CBA.AX (1mo, 1d)
            YF -->> SC: OHLCV data
            SC -->>- AR: { ohlc_series[], indicators{} }
        end
        AR -->>- Client: 200 EventDataset{ quote + ohlc }
    else Cache miss
        SS -->>- AR: None
        AR ->>+ SC: fetch_stock_data("CBA.AX")
        SC ->>+ YF: GET chart/v8/CBA.AX (5d, 1d)
        YF -->> SC: quote data
        SC -->>- AR: StockQuote dict
        opt include_ohlc = true
            AR ->>+ SC: fetch_stock_history("CBA.AX", "1mo")
            SC ->>+ YF: GET chart/v8/CBA.AX (1mo, 1d)
            YF -->> SC: OHLCV data
            SC -->>- AR: { ohlc_series[], indicators{} }
        end
        AR -->>- Client: 200 EventDataset{ quote [+ ohlc] }
    end
```

---

### 3.5 GET `/api/sentiment` — Sentiment Analysis for a Stock

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant AR  as AnalysisRoutes
    participant SS  as StorageService
    participant SC  as StockCollector
    participant NC  as NewsCollector
    participant AS  as AnalysisService
    participant YF  as Yahoo Finance API
    participant GN  as Google News RSS

    Client ->>+ AR: GET /api/sentiment?stock=ANZ

    AR -->> AR: _normalise("ANZ") → "ANZ.AX"

    %% ── Load or fetch news ──
    AR ->>+ SS: load_standardised("combined_events.json")
    alt Cache exists
        SS -->> AR: EventDataset
        AR -->> AR: Filter "Stock news" events for ANZ.AX
    else No cache
        SS -->>- AR: None
        AR ->>+ NC: fetch_financial_news()
        NC ->>+ GN: RSS feeds
        GN -->> NC: articles
        NC -->>- AR: list[Article]
        loop For each article
            AR ->>+ AS: analyse_sentiment(title + description)
            AS -->>- AR: (sentiment, impact_score)
            AR ->>+ AS: extract_related_stocks(text, [ANZ.AX])
            AS -->>- AR: related[]
        end
        AR -->> AR: Filter articles mentioning ANZ.AX
    end

    %% ── Load or fetch stock quote ──
    AR ->>+ SC: fetch_stock_data("ANZ.AX")
    SC ->>+ YF: GET chart/v8/ANZ.AX
    YF -->> SC: quote
    SC -->>- AR: StockQuote dict

    %% ── Aggregate sentiment ──
    AR -->> AR: _aggregate_sentiment(news_events)<br/>→ majority vote: positive/negative/neutral

    AR -->>- Client: 200 {<br/>  ticker: "ANZ.AX",<br/>  overall_sentiment: "positive",<br/>  current_price: ...,<br/>  change_percent: ...,<br/>  news_count: N,<br/>  news_events: [...]<br/>}
```

---

### 3.6 Component Interaction Overview

```mermaid
flowchart TD
    subgraph Client Layer
        C([HTTP Client])
    end

    subgraph API Layer
        MA[main.py\nFastAPI App]
        CR[collect_routes.py\nPOST /collect/*]
        AR[analysis_routes.py\nGET /api/*]
    end

    subgraph Service Layer
        SS[storage_service.py\nFile I/O]
        AS[analysis_service.py\nSentiment + Ticker Extract]
    end

    subgraph Collector Layer
        SC[stock_collector.py\nYahoo Finance]
        NC[news_collector.py\nGoogle News RSS]
    end

    subgraph External APIs
        YF[(Yahoo Finance\nChart API)]
        GN[(Google News\nRSS Feed)]
    end

    subgraph File System
        RAW[data/raw/\nnews/ + stocks/]
        STD[data/standardised/\ncombined_events.json\nhistory_events.json]
    end

    C --> MA
    MA --> CR
    MA --> AR

    CR --> SC
    CR --> NC
    CR --> SS
    CR --> AS

    AR --> SC
    AR --> NC
    AR --> SS
    AR --> AS

    SC -->|HTTP GET| YF
    NC -->|HTTP GET| GN

    SS -->|write raw| RAW
    SS -->|read/write| STD
```
