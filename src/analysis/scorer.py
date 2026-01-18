"""
Token scoring system for ranking potential opportunities.

Combines multiple signals into a single score (0-100).
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import structlog

from .patterns import PatternMatch, PatternAnalyzer

logger = structlog.get_logger()


@dataclass
class TokenScore:
    """Represents a scored token with all relevant data."""

    # Identification
    token_address: str
    token_name: str
    token_symbol: str
    pair_address: str

    # Score breakdown
    total_score: int  # 0-100
    pattern_score: int
    liquidity_score: int
    volume_score: int
    momentum_score: int
    risk_score: int  # Negative (penalties)

    # Grade
    grade: str  # A, B, C, D, F

    # Patterns
    patterns: List[PatternMatch]
    pattern_summary: Dict[str, Any]

    # Market data
    price_usd: float
    market_cap: float
    liquidity_usd: float
    volume_24h: float
    price_change_24h: float

    # Metadata
    age_hours: Optional[float]
    is_bags_token: bool
    url: str

    # Alert level
    alert_level: str  # "high", "medium", "low", "none"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "token_address": self.token_address,
            "token_name": self.token_name,
            "token_symbol": self.token_symbol,
            "pair_address": self.pair_address,
            "total_score": self.total_score,
            "pattern_score": self.pattern_score,
            "liquidity_score": self.liquidity_score,
            "volume_score": self.volume_score,
            "momentum_score": self.momentum_score,
            "risk_score": self.risk_score,
            "grade": self.grade,
            "pattern_count": len(self.patterns),
            "pattern_summary": self.pattern_summary,
            "price_usd": self.price_usd,
            "market_cap": self.market_cap,
            "liquidity_usd": self.liquidity_usd,
            "volume_24h": self.volume_24h,
            "price_change_24h": self.price_change_24h,
            "age_hours": self.age_hours,
            "is_bags_token": self.is_bags_token,
            "url": self.url,
            "alert_level": self.alert_level,
        }


class TokenScorer:
    """
    Score tokens based on multiple factors.

    Scoring breakdown:
    - Pattern score (0-40): Based on detected patterns
    - Liquidity score (0-20): Based on liquidity depth
    - Volume score (0-20): Based on trading activity
    - Momentum score (0-20): Based on price action
    - Risk penalties (-30 to 0): Deductions for red flags
    """

    def __init__(self):
        self.pattern_analyzer = PatternAnalyzer()

    def score_token(
        self,
        token_data: Dict[str, Any],
        bags_data: Optional[Dict[str, Any]] = None,
    ) -> TokenScore:
        """
        Calculate comprehensive score for a token.

        Args:
            token_data: Normalized token data from DexScreener
            bags_data: Optional Bags.fm enrichment data

        Returns:
            TokenScore with all metrics
        """
        # Run pattern analysis
        patterns = self.pattern_analyzer.analyze_all_patterns(token_data, bags_data)
        pattern_summary = self.pattern_analyzer.get_pattern_summary(patterns)

        # Calculate individual scores
        pattern_score = self._calculate_pattern_score(patterns)
        liquidity_score = self._calculate_liquidity_score(token_data)
        volume_score = self._calculate_volume_score(token_data)
        momentum_score = self._calculate_momentum_score(token_data)
        risk_score = self._calculate_risk_score(token_data, patterns)

        # Calculate total (clamped to 0-100)
        total_score = max(0, min(100,
            pattern_score + liquidity_score + volume_score + momentum_score + risk_score
        ))

        # Determine grade
        grade = self._score_to_grade(total_score)

        # Determine alert level
        alert_level = self._determine_alert_level(total_score, patterns)

        return TokenScore(
            token_address=token_data.get("token_address", ""),
            token_name=token_data.get("token_name", "Unknown"),
            token_symbol=token_data.get("token_symbol", "???"),
            pair_address=token_data.get("pair_address", ""),
            total_score=total_score,
            pattern_score=pattern_score,
            liquidity_score=liquidity_score,
            volume_score=volume_score,
            momentum_score=momentum_score,
            risk_score=risk_score,
            grade=grade,
            patterns=patterns,
            pattern_summary=pattern_summary,
            price_usd=token_data.get("price_usd", 0),
            market_cap=token_data.get("market_cap", 0),
            liquidity_usd=token_data.get("liquidity_usd", 0),
            volume_24h=token_data.get("volume_h24", 0),
            price_change_24h=token_data.get("price_change_h24", 0),
            age_hours=token_data.get("age_hours"),
            is_bags_token=bags_data.get("is_bags_token", False) if bags_data else False,
            url=token_data.get("url", ""),
            alert_level=alert_level,
        )

    def _calculate_pattern_score(
        self,
        patterns: List[PatternMatch],
    ) -> int:
        """
        Calculate score from detected patterns (max 40 points).

        Positive patterns add points, negative patterns subtract.
        """
        total_impact = sum(p.score_impact * p.confidence for p in patterns)

        # Scale to 0-40 range
        # Assuming max reasonable positive impact is ~100
        scaled = (total_impact / 100) * 40

        return max(0, min(40, int(scaled)))

    def _calculate_liquidity_score(
        self,
        token_data: Dict[str, Any],
    ) -> int:
        """
        Calculate liquidity score (max 20 points).

        Based on liquidity depth:
        - < $5k: 0 points
        - $5k-$10k: 5 points
        - $10k-$50k: 10 points
        - $50k-$100k: 15 points
        - > $100k: 20 points
        """
        liquidity = token_data.get("liquidity_usd", 0)

        if liquidity < 5000:
            return 0
        elif liquidity < 10000:
            return 5
        elif liquidity < 50000:
            return 10
        elif liquidity < 100000:
            return 15
        else:
            return 20

    def _calculate_volume_score(
        self,
        token_data: Dict[str, Any],
    ) -> int:
        """
        Calculate volume score (max 20 points).

        Based on 24h volume and volume/liquidity ratio.
        """
        volume = token_data.get("volume_h24", 0)
        liquidity = token_data.get("liquidity_usd", 1)

        score = 0

        # Base volume score
        if volume < 1000:
            score = 0
        elif volume < 10000:
            score = 5
        elif volume < 50000:
            score = 10
        elif volume < 100000:
            score = 15
        else:
            score = 18

        # Bonus for high volume/liquidity ratio
        vol_liq_ratio = volume / liquidity
        if vol_liq_ratio > 2:
            score = min(20, score + 2)

        return score

    def _calculate_momentum_score(
        self,
        token_data: Dict[str, Any],
    ) -> int:
        """
        Calculate momentum score (max 20 points).

        Based on price changes and buy/sell ratio.
        """
        change_1h = token_data.get("price_change_h1", 0)
        change_24h = token_data.get("price_change_h24", 0)
        buy_sell_ratio = token_data.get("buy_sell_ratio", 1)

        score = 0

        # Price momentum (up to 12 points)
        if change_1h > 10 and change_24h > 20:
            score += 12
        elif change_1h > 5 and change_24h > 10:
            score += 8
        elif change_1h > 0 and change_24h > 0:
            score += 4
        elif change_1h < -10 or change_24h < -30:
            score += 0  # No momentum points
        else:
            score += 2

        # Buy pressure (up to 8 points)
        if buy_sell_ratio > 2:
            score += 8
        elif buy_sell_ratio > 1.5:
            score += 6
        elif buy_sell_ratio > 1:
            score += 4
        elif buy_sell_ratio > 0.7:
            score += 2

        return min(20, score)

    def _calculate_risk_score(
        self,
        token_data: Dict[str, Any],
        patterns: List[PatternMatch],
    ) -> int:
        """
        Calculate risk penalty (0 to -30).

        Deductions for red flags.
        """
        penalty = 0

        # Low liquidity penalty
        liquidity = token_data.get("liquidity_usd", 0)
        if liquidity < 5000:
            penalty -= 10
        elif liquidity < 2000:
            penalty -= 20

        # Sharp dump penalty
        change_1h = token_data.get("price_change_h1", 0)
        if change_1h < -20:
            penalty -= 15
        elif change_1h < -10:
            penalty -= 5

        # Heavy selling pressure
        buy_sell_ratio = token_data.get("buy_sell_ratio", 1)
        if buy_sell_ratio < 0.5:
            penalty -= 10

        # Bearish patterns
        bearish_patterns = [p for p in patterns if p.score_impact < 0]
        for p in bearish_patterns:
            if "warning" in p.name or "dump" in p.name:
                penalty -= 5

        return max(-30, penalty)

    def _score_to_grade(self, score: int) -> str:
        """Convert numeric score to letter grade."""
        if score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"

    def _determine_alert_level(
        self,
        score: int,
        patterns: List[PatternMatch],
    ) -> str:
        """
        Determine alert level for Telegram notifications.

        Returns: "high", "medium", "low", or "none"
        """
        # Check for volume surge (immediate alert trigger)
        has_volume_surge = any(p.name == "volume_surge" for p in patterns)

        if score >= 80 or (score >= 70 and has_volume_surge):
            return "high"
        elif score >= 70:
            return "medium"
        elif score >= 60:
            return "low"
        else:
            return "none"

    def filter_and_rank(
        self,
        scores: List[TokenScore],
        min_score: int = 60,
        min_liquidity: float = 5000,
    ) -> List[TokenScore]:
        """
        Filter and rank tokens by score.

        Args:
            scores: List of TokenScore objects
            min_score: Minimum score to include
            min_liquidity: Minimum liquidity to include

        Returns:
            Filtered and sorted list of TokenScore objects
        """
        filtered = [
            s for s in scores
            if s.total_score >= min_score
            and s.liquidity_usd >= min_liquidity
            and s.alert_level != "none"
        ]

        # Sort by score descending
        filtered.sort(key=lambda s: s.total_score, reverse=True)

        return filtered
