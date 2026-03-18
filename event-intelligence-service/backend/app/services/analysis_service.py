#simple keyword-based sentiment analysis for financial news
#lightweight approach - no heavy nlp dependencies needed

NEGATIVE_WORDS = {
    "drop", "drops", "dropped", "dropping",
    "fall", "falls", "falling", "fallen",
    "crash", "crashes", "crashed", "crashing",
    "decline", "declines", "declined", "declining",
    "loss", "losses",
    "negative", "bearish",
    "recession", "crisis",
    "warning", "warns", "warned",
    "concern", "concerns", "concerned",
    "risk", "risks",
    "down", "downside", "downturn",
    "plunge", "plunges", "plunged", "plunging",
    "slump", "slumps", "slumped", "slumping",
    "tumble", "tumbles", "tumbled", "tumbling",
    "sell-off", "selloff",
    "volatility", "volatile",
    "uncertainty", "uncertain",
    "cut", "cuts",
    "miss", "misses", "missed",
    "disappoint", "disappoints", "disappointed", "disappointing",
    "weak", "weaker", "weakness", "weakened",
    "slow", "slowing", "slowdown", "slowed",
    "fear", "fears", "feared",
    "weigh", "weighs", "weighed", "weighing",
    "pressure", "pressures", "pressured",
    "struggle", "struggles", "struggling",
    "hike", "hikes",
}

POSITIVE_WORDS = {
    "rise", "rises", "risen", "rising",
    "gain", "gains", "gained", "gaining",
    "surge", "surges", "surged", "surging",
    "rally", "rallies", "rallied", "rallying",
    "growth", "grow", "grew", "grown",
    "positive", "bullish",
    "record", "high", "higher", "highest",
    "strong", "stronger", "strengthen", "strengthened",
    "boost", "boosts", "boosted", "boosting",
    "up", "upside", "uptick",
    "jump", "jumps", "jumped", "jumping",
    "soar", "soars", "soared", "soaring",
    "climb", "climbs", "climbed", "climbing",
    "recovery", "recover", "recovers", "recovered",
    "rebound", "rebounds", "rebounded", "rebounding",
    "profit", "profits", "profitable",
    "beat", "beats",
    "outperform", "outperforms", "outperforming",
    "optimistic", "optimism",
    "confidence", "confident",
    "lift", "lifts", "lifted", "lifting",
    "advance", "advances", "advanced", "advancing",
    "steady", "steadies", "steadied",
}


def analyse_sentiment(text: str) -> tuple[str, float]:
    #returns (sentiment, impact_score); sentiment is positive/negative/neutral, score 0.0-1.0
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
    #extract mentioned asx tickers from text e.g. bhp, cba
    text_upper = text.upper()
    found = []
    for t in known_tickers:
        base = t.replace(".AX", "")
        if base in text_upper or t in text_upper:
            found.append(t if t.endswith(".AX") else f"{base}.AX")
    return list(set(found))
