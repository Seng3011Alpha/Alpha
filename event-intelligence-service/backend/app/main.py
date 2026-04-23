import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# Logging must be configured before observability.py is imported
# so that grafana_cloud_push_enabled/disabled is visible in the logs
from pythonjsonlogger import jsonlogger
_handler = logging.StreamHandler()
_handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)

import app.observability  # noqa: E402

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.routes import collect_router, analysis_router

app = FastAPI(
    title="Tickertone API",
    description="Stock + News sentiment for ASX traders",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# OTel: auto-instruments all routes (http.server.duration etc.)
FastAPIInstrumentor.instrument_app(app)

app.include_router(collect_router)
app.include_router(analysis_router)


@app.on_event("startup")
def on_startup():
    logger.info("startup", extra={"version": "0.1.0"})


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round(time.time() - start, 3)
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_seconds": duration,
        },
    )
    return response


@app.get("/metrics", include_in_schema=False)
def metrics_endpoint(request: Request):
    token = os.environ.get("METRICS_BEARER_TOKEN")
    if token:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="Unauthorized")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
def root():
    return {"message": "Tickertone API", "docs": "/docs"}


@app.get("/debug/env", include_in_schema=False)
def debug_env():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    return {"anthropic_key_set": bool(key), "anthropic_key_prefix": key[:10] if key else ""}

