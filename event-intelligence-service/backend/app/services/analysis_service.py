"""
Simple keyword-based sentiment analysis for financial news.
Lightweight for student project - no heavy NLP dependencies.
"""

NEGATIVE_WORDS = {
    "drop", "fall", "crash", "decline", "loss", "negative", "bearish",
    "recession", "crisis", "warning", "concern", "risk", "down", "plunge",
    "slump", "tumble", "sell-off", "volatility", "uncertainty", "cut",
    "miss", "disappoint", "weak", "slow", "fear",
}

POSITIVE_WORDS = {
    "rise", "gain", "surge", "rally", "growth", "positive", "bullish",
    "record", "high", "strong", "boost", "up", "jump", "soar", "climb",
    "recovery", "profit", "beat", "outperform", "optimistic", "confidence",
}


def analyze_sentiment(text: str) -> tuple[str, float]:
    """
    Returns (sentiment, impact_score).
    sentiment: "positive" | "negative" | "neutral"
    impact_score: 0.0 to 1.0
    """
    if not text:
        return "neutral", 0.0

    words = set(text.lower().replace(".", " ").replace(",", " ").split())
    pos_count = len(words & POSITIVE_WORDS)
    neg_count = len(words & NEGATIVE_WORDS)

    if pos_count > neg_count:
        score = min(0.5 + (pos_count - neg_count) * 0.15, 1.0)
        return "positive", round(score, 2)
    if neg_count > pos_count:
        score = min(0.5 + (neg_count - pos_count) * 0.15, 1.0)
        return "negative", round(score, 2)
    return "neutral", 0.5


def extract_related_stocks(text: str, known_tickers: list[str]) -> list[str]:
    """Extract mentioned ASX tickers from text (e.g. BHP, CBA)."""
    text_upper = text.upper()
    found = []
    for t in known_tickers:
        base = t.replace(".AX", "")
        if base in text_upper or t in text_upper:
            found.append(t if t.endswith(".AX") else f"{base}.AX")
    return list(set(found))
