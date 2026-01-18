"""
Tests for pattern detection algorithms.
"""

import pytest
from src.analysis.patterns import PatternAnalyzer, PatternMatch


class TestPatternAnalyzer:
    """Test the PatternAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = PatternAnalyzer()

    def test_volume_surge_detection(self):
        """Test detection of volume surge pattern."""
        token_data = {
            "volume_h24": 100000,
            "volume_h6": 80000,  # Most volume in last 6h
            "volume_h1": 50000,  # Major spike in last hour
            "liquidity_usd": 20000,
        }

        patterns = self.analyzer._analyze_volume_patterns(token_data)
        pattern_names = [p.name for p in patterns]

        assert "extreme_volume" in pattern_names  # 100k/20k = 5x
        assert "volume_surge" in pattern_names

    def test_bullish_momentum_detection(self):
        """Test detection of bullish momentum."""
        token_data = {
            "price_change_h1": 10,
            "price_change_h6": 25,
            "price_change_h24": 50,
        }

        patterns = self.analyzer._analyze_price_patterns(token_data)
        pattern_names = [p.name for p in patterns]

        assert "strong_bullish_momentum" in pattern_names
        assert "consistent_gains" in pattern_names

    def test_low_liquidity_warning(self):
        """Test low liquidity warning detection."""
        token_data = {
            "liquidity_usd": 2000,
        }

        patterns = self.analyzer._analyze_liquidity_patterns(token_data)
        pattern_names = [p.name for p in patterns]

        assert "low_liquidity_warning" in pattern_names

    def test_ai_theme_detection(self):
        """Test AI/tech theme keyword detection."""
        token_data = {
            "token_name": "AI Agent Helper",
            "token_symbol": "AIHELP",
        }

        patterns = self.analyzer._analyze_name_patterns(token_data)
        pattern_names = [p.name for p in patterns]

        assert "strong_theme" in pattern_names or "bullish_theme" in pattern_names

    def test_bearish_keyword_detection(self):
        """Test bearish keyword warning."""
        token_data = {
            "token_name": "Not A Scam Token",
            "token_symbol": "SCAM",
        }

        patterns = self.analyzer._analyze_name_patterns(token_data)
        pattern_names = [p.name for p in patterns]

        assert "bearish_keyword" in pattern_names

    def test_pattern_summary(self):
        """Test pattern summary generation."""
        patterns = [
            PatternMatch("bullish", "Bullish signal", 20, 0.9, {}),
            PatternMatch("strong", "Strong signal", 30, 0.85, {}),
            PatternMatch("warning", "Warning signal", -10, 0.8, {}),
        ]

        summary = self.analyzer.get_pattern_summary(patterns)

        assert summary["total_patterns"] == 3
        assert summary["bullish_count"] == 2
        assert summary["bearish_count"] == 1
        assert summary["net_impact"] == 40  # 20 + 30 - 10


class TestPatternMatch:
    """Test the PatternMatch dataclass."""

    def test_pattern_match_creation(self):
        """Test creating a PatternMatch."""
        pattern = PatternMatch(
            name="test_pattern",
            description="A test pattern",
            score_impact=15,
            confidence=0.8,
            details={"key": "value"},
        )

        assert pattern.name == "test_pattern"
        assert pattern.score_impact == 15
        assert pattern.confidence == 0.8
