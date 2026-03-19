# Event Intelligence Service

ASX stock prices + financial news sentiment for short-medium term traders.

## Setup

```bash
cd event-intelligence-service
pip install -r requirements.txt
# or: cd backend && pip install -r requirements.txt
cp .env.example .env
# Edit .env: NEWS_API_KEY (optional), USE_MOCK_STOCKS=true (fallback when Yahoo blocks)
```

## Run

```bash
cd backend
uvicorn app.main:app --reload
```

## Docker

```bash
cd backend
docker build -t event-intelligence .
docker run -p 8000:8000 event-intelligence
```

Open http://localhost:8000/docs for Swagger UI.

## API Flow

1. **Collect data**: `POST /collect/pipeline` - fetches stocks + news, runs sentiment, saves to `data/standardised/`
2. **Get sentiment**: `GET /api/sentiment?stock=BHP` - returns stock price + related news sentiment
3. **Get events**: `GET /api/events` - returns full ADAGE event dataset

## Project Structure

```
event-intelligence-service/
├── backend/
│   └── app/
│       ├── main.py
│       ├── collectors/     # Yahoo Finance, News API
│       ├── models/         # ADAGE event schema
│       ├── services/       # Storage, sentiment analysis
│       └── routes/         # API endpoints
├── frontend/               # (Sprint 3)
└── requirements.txt
```
