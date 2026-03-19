#simple keyword-based sentiment analysis for financial news
#lightweight approach - no heavy nlp dependencies needed

import re

NEGATIVE_WORDS = {
    #price movement - down
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
    #loss language
    "crash", "crashes", "crashed", "crashing",
    "decline", "declines", "declined", "declining",
    "loss", "losses", "lose", "loses", "lost", "losing",
    "sell-off", "selloff",
    "down", "downside", "downturn", "downgrade", "downgraded",
    "red",
    #financial distress
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
    #price movement - up
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
    #recovery language
    "recovery", "recover", "recovers", "recovered",
    "rebound", "rebounds", "rebounded", "rebounding",
    "steady", "steadies", "steadied",
    #financial strength
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


def analyse_sentiment(text: str) -> tuple[str, float]:
    #returns (sentiment, impact_score); sentiment is positive/negative/neutral, score 0.0-1.0
    if not text:
        return "neutral", 0.0

    #strip punctuation (except hyphens) before tokenising so e.g. "drops;" matches "drops"
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


def extract_related_stocks(text: str, known_tickers: list[str]) -> list[str]:
    #extract mentioned asx tickers from text e.g. bhp, cba
    text_upper = text.upper()
    found = []
    for t in known_tickers:
        base = t.replace(".AX", "").upper()
        if base in text_upper:
            found.append(f"{base}.AX")
    return list(set(found))
