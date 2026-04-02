import logging
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from pythonjsonlogger import jsonlogger

from app.routes import collect_router, analysis_router

# JSON structured logging to stdout
_handler = logging.StreamHandler()
_handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Event Intelligence API",
    description="Stock + News sentiment for ASX traders",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus: auto-instruments all routes and exposes /metrics
Instrumentator().instrument(app).expose(app)

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


@app.get("/")
def root():
    return {"message": "Event Intelligence API", "docs": "/docs"}
