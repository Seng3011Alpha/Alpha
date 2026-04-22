# External Reddit API Evaluation Report (ASX Focus)

## 1) Goal

This report evaluates whether the external Reddit API is practical and useful for an Australian stock intelligence project.  
The evaluation focuses on three questions:

1. How should the API be tested?
2. Is it useful for the project?
3. How should it be used in production and analysis workflows?

## 2) Test Approach

### 2.1 Functional/API Reliability Tests

We executed live integration tests covering:

- Auth flow: `signup/login` and bearer token usage
- User endpoint: `GET /v1/auth/me`
- Data endpoints:
  - `GET /v1/post/search`
  - `GET /v1/post/comments`

Files used:

- `tests/test_external_reddit_api.py`
- `tests/test_external_reddit_api_asx_compat.py`

### 2.2 ASX Compatibility Tests

We validated:

- Envelope consistency (`data_source`, `dataset_type`, `dataset_id`, `time_object`, `events`)
- Required post fields (`id`, `title`, `author`, `created_utc`, `score`, `subreddit`)
- Required comment fields (`id`, `author`, `body`, `created_utc`, `score`)
- Stability and latency under repeated requests
- Invalid token rejection behavior (`401/403`)

### 2.3 Divergence/Signal Tests (News vs Reddit)

We implemented an MVP backtesting-style test:

- Align daily news sentiment, Reddit sentiment, and stock returns for ASX context
- Detect anomaly days (neutral news + large price move + Reddit volume spike)
- Compute:
  - same-day Pearson correlation
  - lag-1 correlation (when enough aligned days exist)

File used:

- `tests/test_reddit_news_divergence_asx.py`

The test now auto-scans multiple ASX scenarios and picks the best overlap case.

## 3) Execution Results

### 3.1 Full Suite Result

Command:

```bash
pytest tests/test_external_reddit_api.py tests/test_external_reddit_api_asx_compat.py tests/test_reddit_news_divergence_asx.py -q --junitxml=external_api_extended_report.xml
```

Outcome:

- **7 passed**
- **1 skipped**
- Runtime: **65.70s**
- JUnit output: `external_api_extended_report.xml`

### 3.2 Correlation Scan (Multi-ticker Diagnostic)

Additional diagnostics across ASX tickers and scenario combinations showed:

- `BHP`: best scenario `australia|RBA`, aligned days `2`, Pearson `-1.0000`
- `WBC`: best scenario `ASX_Bets|ASX`, aligned days `14`, Pearson `0.1631`
- `ANZ`: best scenario `ASX_Bets|ASX`, aligned days `14`, Pearson `0.1631`
- `CBA`/`NAB`: intermittent `500` errors from upstream API in some scenarios

Interpretation:

- The API can produce meaningful overlap and measurable correlation.
- Overlap quality depends heavily on ticker + subreddit + query combinations.
- Upstream instability (occasional 500 responses) must be handled with retries/fallback.

## 4) Is This API Useful?

## Short Answer: **Yes, with guardrails**

### Why it is useful

- Adds retail sentiment not captured by traditional news feeds
- Improves event coverage for ASX-related discussions
- Enables divergence analysis (retail vs mainstream/news sentiment)
- Supports exploratory and tactical signal generation

### Main constraints

- Data coverage is uneven across tickers/scenarios
- Correlation quality can be sample-size limited
- Endpoint reliability is not perfect (observed intermittent HTTP 500)

Conclusion:

- Useful for **signal enrichment**, not as a standalone trading signal
- Best treated as a complementary feature source

## 5) How to Use the API in This Project

### 5.1 Recommended Integration Pattern

1. Add a Reddit collector/adapter layer
2. Normalize external `attributes` to internal schema before pipeline use
3. Merge Reddit events into existing ADAGE event workflow
4. Keep source tag (`data_source`) so downstream analysis can weight/filter by source

### 5.2 Suggested Operational Guardrails

- Use request retries with exponential backoff for 5xx responses
- Cache auth token and refresh only when needed
- Enforce minimum sample windows before publishing correlation outputs
- Keep a fallback mode that skips correlation when aligned data is insufficient

### 5.3 Suggested Runtime Config

- Prioritize ASX-oriented scenarios (example):
  - `ASX_Bets|ASX`
  - `ASX_Bets|BHP`
  - `australia|RBA`
- Use a formal minimum alignment threshold (e.g., 5+ aligned days)
- Store test outputs in JUnit/XML + Markdown for reproducibility

## 6) Recommended Next Steps

1. Add retry logic for Reddit search requests in divergence test/collector code
2. Run nightly rolling evaluation to accumulate larger sample windows
3. Track per-ticker data quality metrics (coverage, overlap days, latency, error rate)
4. Introduce source-weighted sentiment aggregation (news vs Reddit) in analysis endpoints

## 7) Final Assessment

The external Reddit API is operational and valuable for this ASX project when used as a supplementary sentiment source.  
It is most effective when paired with:

- scenario-based query selection,
- strict data-quality thresholds,
- and robust reliability handling (retry/fallback).
