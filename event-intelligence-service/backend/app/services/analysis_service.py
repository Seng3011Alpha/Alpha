#sentiment analysis for financial news
#primary path uses anthropic claude; falls back to keyword scoring when key missing or call fails

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

NEGATIVE_WORDS = {
    "drop", "drops", "dropped", "dropping",
    "fall", "falls", "falling", "fallen",
    "dive", "dives", "dived", "diving",
    "slide", "slides", "slid", "sliding",
    "slip", "slips", "slipped", "slipping",
    "sink", "sinks", "sank", "sinking",
    "dip", "dips", "dipped", "dipping",
    "lower", "lowest",
    "plunge", "plunges", "plunged", "plunging",
    "slump", "slumps", "slumped", "slumping",
    "tumble", "tumbles", "tumbled", "tumbling",
    "retreat", "retreats", "retreated", "retreating",
    "tank", "tanks", "tanked", "tanking",
    "shed", "sheds",
    "crash", "crashes", "crashed", "crashing",
    "decline", "declines", "declined", "declining",
    "loss", "losses", "lose", "loses", "lost", "losing",
    "sell-off", "selloff",
    "down", "downside", "downturn", "downgrade", "downgraded",
    "red",
    "negative", "bearish",
    "recession", "crisis",
    "warning", "warns", "warned",
    "concern", "concerns", "concerned",
    "risk", "risks", "risky",
    "volatility", "volatile",
    "uncertainty", "uncertain",
    "cut", "cuts", "cutting",
    "miss", "misses", "missed",
    "disappoint", "disappoints", "disappointed", "disappointing",
    "weak", "weaker", "weakness", "weakened",
    "slow", "slowing", "slowdown", "slowed",
    "fear", "fears", "feared",
    "weigh", "weighs", "weighed", "weighing",
    "pressure", "pressures", "pressured",
    "struggle", "struggles", "struggling",
    "hike", "hikes",
    "headwinds", "headwind",
    "shellacking", "shellacked",
    "hell", "nears", "rotation",
}

POSITIVE_WORDS = {
    "rise", "rises", "risen", "rising",
    "gain", "gains", "gained", "gaining",
    "surge", "surges", "surged", "surging",
    "rally", "rallies", "rallied", "rallying",
    "climb", "climbs", "climbed", "climbing",
    "jump", "jumps", "jumped", "jumping",
    "soar", "soars", "soared", "soaring",
    "lift", "lifts", "lifted", "lifting",
    "advance", "advances", "advanced", "advancing",
    "up", "upside", "uptick",
    "higher", "highest",
    "recovery", "recover", "recovers", "recovered",
    "rebound", "rebounds", "rebounded", "rebounding",
    "steady", "steadies", "steadied",
    "growth", "grow", "grew", "grown",
    "positive", "bullish",
    "record", "high", "strong", "stronger", "strengthen", "strengthened",
    "boost", "boosts", "boosted", "boosting",
    "profit", "profits", "profitable",
    "beat", "beats",
    "outperform", "outperforms", "outperforming",
    "optimistic", "optimism",
    "confidence", "confident",
    "thrive", "thrives", "thrived", "thriving",
    "upgrade", "upgraded", "upgrades",
    "win", "wins", "winning", "won",
    "lead", "leads", "leading", "led",
    "exceed", "exceeds", "exceeded", "exceeding",
    "green", "best",
    "overtake", "overtakes", "overtook",
}

SENTIMENT_MODEL = os.getenv("ANTHROPIC_SENTIMENT_MODEL", "claude-haiku-4-5-20251001")
_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "sentiment_cache.json"


def _fallback_sentiment(text: str) -> tuple[str, float]:
    if not text:
        return "neutral", 0.0
    words = set(re.sub(r"[^\w\s-]", " ", text.lower()).split())
    pos_count = len(words & POSITIVE_WORDS)
    neg_count = len(words & NEGATIVE_WORDS)
    if pos_count > neg_count:
        score = min(0.5 + (pos_count - neg_count) * 0.15, 1.0)
        return "positive", round(score, 2)
    if neg_count > pos_count:
        score = min(0.5 + (neg_count - pos_count) * 0.15, 1.0)
        return "negative", round(score, 2)
    return "neutral", 0.5


def analyse_sentiment(text: str) -> tuple[str, float]:
    #kept for tests and as fallback; prefer analyse_sentiment_llm
    return _fallback_sentiment(text)


def _load_cache() -> dict[str, dict]:
    try:
        if _CACHE_PATH.exists():
            with _CACHE_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def _save_cache(cache: dict[str, dict]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _CACHE_PATH.open("w", encoding="utf-8") as f:
            json.dump(cache, f)
    except OSError as e:
        logger.warning("sentiment_cache_write_failed", extra={"error": str(e)})


def _key(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:16]


def _get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
        return Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic_sdk_missing")
        return None


_SENTIMENT_SYSTEM = (
    "You are a financial news sentiment classifier for ASX markets. "
    "Given one news snippet, reply with strict JSON: "
    '{"sentiment":"positive"|"negative"|"neutral","score":0.0-1.0}. '
    "Score is the confidence magnitude (higher means more decisive). "
    "Neutral articles should score around 0.4 to 0.6. "
    "Return JSON only, no prose."
)


def analyse_sentiment_llm(text: str) -> tuple[str, float]:
    #primary sentiment path; falls back to keyword scoring on any failure
    if not text or not text.strip():
        return "neutral", 0.0

    cache = _load_cache()
    k = _key(text)
    if k in cache:
        entry = cache[k]
        return entry["sentiment"], float(entry["score"])

    client = _get_client()
    if client is None:
        return _fallback_sentiment(text)

    from app.observability import record_llm_call

    try:
        started = time.time()
        msg = client.messages.create(
            model=SENTIMENT_MODEL,
            max_tokens=80,
            system=_SENTIMENT_SYSTEM,
            messages=[{"role": "user", "content": text[:1200]}],
        )
        record_llm_call("sentiment", time.time() - started)
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        data = _extract_json(raw)
        sentiment = str(data.get("sentiment", "neutral")).lower()
        if sentiment not in {"positive", "negative", "neutral"}:
            sentiment = "neutral"
        score = float(data.get("score", 0.5))
        score = max(0.0, min(score, 1.0))
        cache[k] = {"sentiment": sentiment, "score": round(score, 2)}
        _save_cache(cache)
        return sentiment, round(score, 2)
    except Exception as e:
        logger.warning("llm_sentiment_failed", extra={"error": str(e)})
        return _fallback_sentiment(text)


def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]*\}", raw)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
    return {}


def analyse_sentiment_batch(texts: Iterable[str]) -> list[tuple[str, float]]:
    return [analyse_sentiment_llm(t) for t in texts]


def extract_related_stocks(text: str, known_tickers: list[str]) -> list[str]:
    text_upper = text.upper()
    found = []
    for t in known_tickers:
        base = t.replace(".AX", "").upper()
        if base in text_upper:
            found.append(f"{base}.AX")
    return list(set(found))
