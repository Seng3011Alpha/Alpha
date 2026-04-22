#written stock report synthesised by claude sonnet from quote plus news plus indicators
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPORT_MODEL = os.getenv("ANTHROPIC_REPORT_MODEL", "claude-sonnet-4-6")
_REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"

_SYSTEM_PROMPT = (
    "You are a careful equities analyst writing for retail investors. "
    "Summarise the supplied material about a single ASX-listed company in British English. "
    "Use only the facts provided. Do not invent numbers. If evidence is thin, say so. "
    "Return strict JSON with this shape and nothing else: "
    '{"summary": "3-5 short paragraphs of markdown", '
    '"key_drivers": ["short bullet", ...], '
    '"risks": ["short bullet", ...], '
    '"overall_sentiment": "positive"|"negative"|"neutral"}. '
    "Markdown in summary may use bold and line breaks but no headings."
)


def _cache_path(ticker: str) -> Path:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return _REPORTS_DIR / f"{ticker.upper()}_{day}.json"


def _load_cached(ticker: str) -> dict | None:
    p = _cache_path(ticker)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _save_cached(ticker: str, payload: dict) -> None:
    try:
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        with _cache_path(ticker).open("w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError as e:
        logger.warning("report_cache_write_failed", extra={"error": str(e)})


def _get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
        return Anthropic(api_key=api_key)
    except ImportError:
        return None


def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
    return {}


def _fallback_report(ticker: str, quote: dict | None, news: list[dict], indicators: dict | None) -> dict:
    pos = sum(1 for n in news if n.get("sentiment") == "positive")
    neg = sum(1 for n in news if n.get("sentiment") == "negative")
    overall = "positive" if pos > neg else "negative" if neg > pos else "neutral"
    price_line = ""
    if quote:
        price_line = (
            f"**{ticker}** last traded at {quote.get('Quote Price')} "
            f"({quote.get('change_percent')}% vs previous close)."
        )
    summary = (
        f"{price_line}\n\n"
        f"Across {len(news)} recent articles, {pos} were positive and {neg} were negative. "
        "No language model is configured, so this is a keyword-based summary. "
        "Set ANTHROPIC_API_KEY to enable full analyst commentary."
    ).strip()
    return {
        "summary": summary,
        "key_drivers": [n.get("title", "")[:140] for n in news if n.get("sentiment") == "positive"][:3],
        "risks": [n.get("title", "")[:140] for n in news if n.get("sentiment") == "negative"][:3],
        "overall_sentiment": overall,
    }


def _build_user_prompt(ticker: str, quote: dict | None, news: list[dict], indicators: dict | None) -> str:
    lines: list[str] = [f"Company ticker: {ticker}"]
    if quote:
        lines.append("Latest quote:")
        for k in ("company", "Quote Price", "Previous Close", "Open", "Volume", "change_percent"):
            if k in quote:
                lines.append(f"  {k}: {quote[k]}")
    if indicators:
        lines.append("Technical indicators (1 month):")
        for k in ("MA5", "MA20", "volatility_annual_pct", "week52_high", "week52_low", "days_high", "days_low"):
            if k in indicators:
                lines.append(f"  {k}: {indicators[k]}")
    lines.append(f"Recent news ({len(news)} articles):")
    for i, n in enumerate(news, start=1):
        lines.append(
            f"  {i}. [{n.get('sentiment', 'neutral')} {n.get('impact_score', 0)}] "
            f"{n.get('source', 'unknown')}: {n.get('title', '')}"
        )
    return "\n".join(lines)


def generate_stock_report(
    ticker: str,
    quote: dict | None,
    news: list[dict],
    indicators: dict | None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    ticker = ticker.upper()
    if not force_refresh:
        cached = _load_cached(ticker)
        if cached:
            cached["cached"] = True
            return cached

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    client = _get_client()
    if client is None:
        body = _fallback_report(ticker, quote, news, indicators)
        payload = {
            "stock": ticker,
            "generated_at": now_iso,
            "model": "fallback",
            **body,
            "articles_considered": len(news),
            "cached": False,
        }
        _save_cached(ticker, payload)
        return payload

    from app.observability import record_llm_call

    prompt = _build_user_prompt(ticker, quote, news, indicators)

    try:
        started = time.time()
        msg = client.messages.create(
            model=REPORT_MODEL,
            max_tokens=1200,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        record_llm_call("report", time.time() - started)
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        body = _extract_json(raw)
        if not body or "summary" not in body:
            body = _fallback_report(ticker, quote, news, indicators)
            model_used = "fallback"
        else:
            model_used = REPORT_MODEL
    except Exception as e:
        logger.warning("llm_report_failed", extra={"error": str(e)})
        body = _fallback_report(ticker, quote, news, indicators)
        model_used = "fallback"

    overall = str(body.get("overall_sentiment", "neutral")).lower()
    if overall not in {"positive", "negative", "neutral"}:
        overall = "neutral"

    payload = {
        "stock": ticker,
        "generated_at": now_iso,
        "model": model_used,
        "summary": body.get("summary", ""),
        "key_drivers": list(body.get("key_drivers", []))[:5],
        "risks": list(body.get("risks", []))[:5],
        "overall_sentiment": overall,
        "articles_considered": len(news),
        "cached": False,
    }
    _save_cached(ticker, payload)
    return payload
