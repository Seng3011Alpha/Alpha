from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import collect_router, analysis_router

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

app.include_router(collect_router)
app.include_router(analysis_router)

@app.get("/")
def root():
    return {"message": "Event Intelligence API", "docs": "/docs"}
