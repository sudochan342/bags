"""
Tests for token scoring system.
"""

import pytest
from src.analysis.scorer import TokenScorer, TokenScore


class TestTokenScorer:
    """Test the TokenScorer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = TokenScorer()

    def test_score_high_quality_token(self):
        """Test scoring a high-quality token."""
        token_data = {
            "token_address": "test123",
            "token_name": "AI Agent Token",
            "token_symbol": "AIAGENT",
            "pair_address": "pair123",
            "price_usd": 0.001,
            "market_cap": 500000,
            "liquidity_usd": 75000,
            "volume_h24": 150000,
            "volume_h6": 80000,
            "volume_h1": 40000,
            "price_change_h1": 15,
            "price_change_h6": 30,
            "price_change_h24": 50,
            "buys_24h": 200,
            "sells_24h": 80,
            "total_txns_24h": 280,
            "buy_sell_ratio": 2.5,
            "age_hours": 48,
            "url": "https://dexscreener.com/solana/test",
        }

        score = self.scorer.score_token(token_data)

        assert score.total_score >= 70
        assert score.grade in ["A", "B"]
        assert score.alert_level in ["high", "medium"]

    def test_score_low_quality_token(self):
        """Test scoring a low-quality token."""
        token_data = {
            "token_address": "test456",
            "token_name": "Random Token",
            "token_symbol": "RND",
            "pair_address": "pair456",
            "price_usd": 0.0001,
            "market_cap": 10000,
            "liquidity_usd": 2000,  # Very low
            "volume_h24": 500,  # Very low
            "volume_h6": 200,
            "volume_h1": 50,
            "price_change_h1": -25,  # Dumping
            "price_change_h6": -40,
            "price_change_h24": -60,
            "buys_24h": 5,
            "sells_24h": 20,  # More sells
            "total_txns_24h": 25,
            "buy_sell_ratio": 0.25,
            "age_hours": 2,
            "url": "https://dexscreener.com/solana/test",
        }

        score = self.scorer.score_token(token_data)

        assert score.total_score < 50
        assert score.grade in ["D", "F"]
        assert score.alert_level == "none"

    def test_liquidity_score_calculation(self):
        """Test liquidity score calculation."""
        # Test various liquidity levels
        test_cases = [
            (1000, 0),      # Very low
            (7500, 5),      # Low
            (25000, 10),    # Medium
            (75000, 15),    # Good
            (150000, 20),   # Excellent
        ]

        for liquidity, expected_score in test_cases:
            token_data = {"liquidity_usd": liquidity}
            score = self.scorer._calculate_liquidity_score(token_data)
            assert score == expected_score, f"Liquidity {liquidity} should give score {expected_score}, got {score}"

    def test_grade_assignment(self):
        """Test grade assignment from scores."""
        test_cases = [
            (95, "A"),
            (80, "A"),
            (75, "B"),
            (65, "C"),
            (55, "D"),
            (40, "F"),
        ]

        for score, expected_grade in test_cases:
            grade = self.scorer._score_to_grade(score)
            assert grade == expected_grade, f"Score {score} should give grade {expected_grade}, got {grade}"

    def test_filter_and_rank(self):
        """Test filtering and ranking tokens."""
        # Create mock scores
        scores = [
            TokenScore(
                token_address="a",
                token_name="Token A",
                token_symbol="A",
                pair_address="pa",
                total_score=85,
                pattern_score=30,
                liquidity_score=20,
                volume_score=20,
                momentum_score=15,
                risk_score=0,
                grade="A",
                patterns=[],
                pattern_summary={},
                price_usd=0.001,
                market_cap=100000,
                liquidity_usd=50000,
                volume_24h=100000,
                price_change_24h=20,
                age_hours=24,
                is_bags_token=True,
                url="",
                alert_level="high",
            ),
            TokenScore(
                token_address="b",
                token_name="Token B",
                token_symbol="B",
                pair_address="pb",
                total_score=55,
                pattern_score=15,
                liquidity_score=10,
                volume_score=15,
                momentum_score=15,
                risk_score=0,
                grade="D",
                patterns=[],
                pattern_summary={},
                price_usd=0.001,
                market_cap=50000,
                liquidity_usd=10000,
                volume_24h=20000,
                price_change_24h=5,
                age_hours=48,
                is_bags_token=False,
                url="",
                alert_level="none",
            ),
        ]

        filtered = self.scorer.filter_and_rank(scores, min_score=60)

        assert len(filtered) == 1
        assert filtered[0].token_symbol == "A"
