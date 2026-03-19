#tests for analysis_service - sentiment scoring and ticker extraction
import pytest
from app.services.analysis_service import analyse_sentiment, extract_related_stocks


class TestAnalyseSentiment:
    def test_empty_string_returns_neutral(self):
        sentiment, score = analyse_sentiment("")
        assert sentiment == "neutral"
        assert score == 0.0

    def test_positive_text(self):
        sentiment, score = analyse_sentiment("ASX surge as BHP profit beats expectations")
        assert sentiment == "positive"
        assert 0.5 < score <= 1.0

    def test_negative_text(self):
        sentiment, score = analyse_sentiment("Market crash and recession fear drives ASX decline")
        assert sentiment == "negative"
        assert 0.5 < score <= 1.0

    def test_neutral_text(self):
        #no positive or negative words so should stay neutral
        sentiment, score = analyse_sentiment("ASX opened today for trading")
        assert sentiment == "neutral"
        assert score == 0.5

    def test_score_capped_at_one(self):
        #pile in loads of positive words to make sure the cap holds
        text = "rise gain surge rally growth positive bullish record high strong boost up jump soar climb profit beat"
        sentiment, score = analyse_sentiment(text)
        assert sentiment == "positive"
        assert score <= 1.0

    def test_returns_tuple(self):
        result = analyse_sentiment("some text")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_score_is_float(self):
        _, score = analyse_sentiment("some text")
        assert isinstance(score, float)

    def test_mixed_leans_positive(self):
        #three positive words vs one negative - should tip positive
        sentiment, _ = analyse_sentiment("rise gain surge drop")
        assert sentiment == "positive"

    def test_mixed_leans_negative(self):
        #four negative words vs one positive
        sentiment, _ = analyse_sentiment("crash decline fall loss rise")
        assert sentiment == "negative"

    def test_case_insensitive(self):
        #uppercase and lowercase input should produce the same result
        lower = analyse_sentiment("surge rally growth")
        upper = analyse_sentiment("SURGE RALLY GROWTH")
        assert lower[0] == upper[0]


class TestExtractRelatedStocks:
    def test_finds_ticker_in_text(self):
        result = extract_related_stocks("BHP reported strong earnings today", ["BHP", "CBA"])
        assert "BHP.AX" in result

    def test_no_match_returns_empty(self):
        result = extract_related_stocks("General market commentary", ["BHP", "CBA"])
        assert result == []

    def test_multiple_tickers_found(self):
        result = extract_related_stocks("BHP and CBA both rose today", ["BHP", "CBA", "NAB"])
        assert "BHP.AX" in result
        assert "CBA.AX" in result
        assert "NAB.AX" not in result

    def test_ax_suffix_in_ticker_input(self):
        #tickers passed in with .AX already appended should still match
        result = extract_related_stocks("BHP rose today", ["BHP.AX"])
        assert "BHP.AX" in result

    def test_no_duplicates(self):
        #ticker mentioned three times but should only appear once in output
        result = extract_related_stocks("BHP BHP BHP", ["BHP"])
        assert len(result) == 1

    def test_empty_known_tickers(self):
        result = extract_related_stocks("BHP rose today", [])
        assert result == []

    def test_empty_text(self):
        result = extract_related_stocks("", ["BHP", "CBA"])
        assert result == []

