"""
Pattern detection algorithms for identifying promising tokens.

Based on analysis of successful Bags.fm tokens (GAS, RALPH, CMEM, VVM):
- AI/Tech themed tokens perform well
- High volume spikes indicate momentum
- Healthy holder distribution is key
- Creator earnings correlate with success
"""

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

from ..config import PATTERN_THRESHOLDS, BULLISH_KEYWORDS, BEARISH_KEYWORDS

logger = structlog.get_logger()


@dataclass
class PatternMatch:
    """Represents a detected pattern."""

    name: str
    description: str
    score_impact: int  # -100 to +100
    confidence: float  # 0.0 to 1.0
    details: Dict[str, Any]


class PatternAnalyzer:
    """
    Analyze tokens for patterns that indicate potential success.

    Patterns are based on analysis of top performing Bags.fm tokens.
    """

    def __init__(self):
        self.thresholds = PATTERN_THRESHOLDS

    def analyze_all_patterns(
        self,
        token_data: Dict[str, Any],
        bags_data: Optional[Dict[str, Any]] = None,
    ) -> List[PatternMatch]:
        """
        Run all pattern detection algorithms on token data.

        Args:
            token_data: Normalized token data from DexScreener
            bags_data: Optional Bags.fm enrichment data

        Returns:
            List of detected patterns
        """
        patterns = []

        # Volume patterns
        patterns.extend(self._analyze_volume_patterns(token_data))

        # Liquidity patterns
        patterns.extend(self._analyze_liquidity_patterns(token_data))

        # Price momentum patterns
        patterns.extend(self._analyze_price_patterns(token_data))

        # Transaction patterns
        patterns.extend(self._analyze_transaction_patterns(token_data))

        # Age patterns
        patterns.extend(self._analyze_age_patterns(token_data))

        # Market cap patterns
        patterns.extend(self._analyze_market_cap_patterns(token_data))

        # Name/theme patterns
        patterns.extend(self._analyze_name_patterns(token_data))

        # Bags.fm specific patterns
        if bags_data and bags_data.get("is_bags_token"):
            patterns.extend(self._analyze_bags_patterns(bags_data))

        return patterns

    def _analyze_volume_patterns(
        self,
        token_data: Dict[str, Any],
    ) -> List[PatternMatch]:
        """Analyze volume-related patterns."""
        patterns = []

        volume_24h = token_data.get("volume_h24", 0)
        volume_6h = token_data.get("volume_h6", 0)
        volume_1h = token_data.get("volume_h1", 0)
        liquidity = token_data.get("liquidity_usd", 1)  # Avoid division by zero

        # Volume to liquidity ratio (indicates trading activity)
        vol_liq_ratio = volume_24h / liquidity if liquidity > 0 else 0

        if vol_liq_ratio > 5:
            patterns.append(PatternMatch(
                name="extreme_volume",
                description=f"Extreme trading activity: {vol_liq_ratio:.1f}x liquidity traded in 24h",
                score_impact=25,
                confidence=0.9,
                details={"volume_24h": volume_24h, "liquidity": liquidity, "ratio": vol_liq_ratio},
            ))
        elif vol_liq_ratio > 2:
            patterns.append(PatternMatch(
                name="high_volume",
                description=f"High trading activity: {vol_liq_ratio:.1f}x liquidity traded in 24h",
                score_impact=15,
                confidence=0.85,
                details={"volume_24h": volume_24h, "liquidity": liquidity, "ratio": vol_liq_ratio},
            ))

        # Volume acceleration (6h vs 24h average)
        if volume_24h > 0:
            avg_6h_from_24h = (volume_24h / 4)  # Expected 6h if evenly distributed
            if volume_6h > avg_6h_from_24h * self.thresholds["volume_spike_multiplier"]:
                patterns.append(PatternMatch(
                    name="volume_acceleration",
                    description="Volume accelerating in recent hours",
                    score_impact=20,
                    confidence=0.8,
                    details={"volume_6h": volume_6h, "expected_6h": avg_6h_from_24h},
                ))

        # Recent volume spike (1h)
        if volume_6h > 0:
            avg_1h_from_6h = (volume_6h / 6)
            if volume_1h > avg_1h_from_6h * self.thresholds["volume_surge_multiplier"]:
                patterns.append(PatternMatch(
                    name="volume_surge",
                    description="Major volume surge in last hour",
                    score_impact=30,
                    confidence=0.85,
                    details={"volume_1h": volume_1h, "expected_1h": avg_1h_from_6h},
                ))

        # Low volume warning
        if volume_24h < 1000:
            patterns.append(PatternMatch(
                name="low_volume_warning",
                description="Very low trading volume",
                score_impact=-20,
                confidence=0.9,
                details={"volume_24h": volume_24h},
            ))

        return patterns

    def _analyze_liquidity_patterns(
        self,
        token_data: Dict[str, Any],
    ) -> List[PatternMatch]:
        """Analyze liquidity-related patterns."""
        patterns = []

        liquidity = token_data.get("liquidity_usd", 0)

        if liquidity >= self.thresholds["strong_liquidity_min"]:
            patterns.append(PatternMatch(
                name="strong_liquidity",
                description=f"Strong liquidity: ${liquidity:,.0f}",
                score_impact=20,
                confidence=0.9,
                details={"liquidity_usd": liquidity},
            ))
        elif liquidity >= self.thresholds["healthy_liquidity_min"]:
            patterns.append(PatternMatch(
                name="healthy_liquidity",
                description=f"Healthy liquidity: ${liquidity:,.0f}",
                score_impact=10,
                confidence=0.85,
                details={"liquidity_usd": liquidity},
            ))
        elif liquidity < 5000:
            patterns.append(PatternMatch(
                name="low_liquidity_warning",
                description=f"Low liquidity risk: ${liquidity:,.0f}",
                score_impact=-15,
                confidence=0.9,
                details={"liquidity_usd": liquidity},
            ))

        return patterns

    def _analyze_price_patterns(
        self,
        token_data: Dict[str, Any],
    ) -> List[PatternMatch]:
        """Analyze price momentum patterns."""
        patterns = []

        change_1h = token_data.get("price_change_h1", 0)
        change_6h = token_data.get("price_change_h6", 0)
        change_24h = token_data.get("price_change_h24", 0)

        # Strong bullish momentum
        if (
            change_1h > self.thresholds["bullish_price_change_1h"]
            and change_24h > self.thresholds["bullish_price_change_24h"]
        ):
            patterns.append(PatternMatch(
                name="strong_bullish_momentum",
                description=f"Strong upward momentum: +{change_1h:.1f}% (1h), +{change_24h:.1f}% (24h)",
                score_impact=25,
                confidence=0.85,
                details={"change_1h": change_1h, "change_24h": change_24h},
            ))
        elif change_1h > self.thresholds["bullish_price_change_1h"]:
            patterns.append(PatternMatch(
                name="bullish_momentum",
                description=f"Bullish momentum: +{change_1h:.1f}% (1h)",
                score_impact=15,
                confidence=0.8,
                details={"change_1h": change_1h},
            ))

        # Consistent gains (all timeframes positive)
        if change_1h > 0 and change_6h > 0 and change_24h > 0:
            patterns.append(PatternMatch(
                name="consistent_gains",
                description="Consistent positive price action across all timeframes",
                score_impact=15,
                confidence=0.8,
                details={"change_1h": change_1h, "change_6h": change_6h, "change_24h": change_24h},
            ))

        # Oversold bounce potential
        if change_24h < -30 and change_1h > 5:
            patterns.append(PatternMatch(
                name="oversold_bounce",
                description="Potential oversold bounce: recovering from -30%+ daily loss",
                score_impact=10,
                confidence=0.6,
                details={"change_1h": change_1h, "change_24h": change_24h},
            ))

        # Dump warning
        if change_1h < -20:
            patterns.append(PatternMatch(
                name="dump_warning",
                description=f"Sharp decline: {change_1h:.1f}% in last hour",
                score_impact=-30,
                confidence=0.9,
                details={"change_1h": change_1h},
            ))

        return patterns

    def _analyze_transaction_patterns(
        self,
        token_data: Dict[str, Any],
    ) -> List[PatternMatch]:
        """Analyze transaction patterns (buys vs sells)."""
        patterns = []

        buys = token_data.get("buys_24h", 0)
        sells = token_data.get("sells_24h", 0)
        total_txns = token_data.get("total_txns_24h", 0)
        buy_sell_ratio = token_data.get("buy_sell_ratio", 1)

        # Strong buying pressure
        if buy_sell_ratio > 2 and buys > 50:
            patterns.append(PatternMatch(
                name="strong_buying_pressure",
                description=f"Strong buying pressure: {buy_sell_ratio:.1f}x more buys than sells",
                score_impact=20,
                confidence=0.85,
                details={"buys": buys, "sells": sells, "ratio": buy_sell_ratio},
            ))
        elif buy_sell_ratio > 1.5 and buys > 30:
            patterns.append(PatternMatch(
                name="buying_pressure",
                description=f"Buying pressure: {buy_sell_ratio:.1f}x more buys than sells",
                score_impact=10,
                confidence=0.8,
                details={"buys": buys, "sells": sells, "ratio": buy_sell_ratio},
            ))

        # Selling pressure warning
        if buy_sell_ratio < 0.5 and sells > 50:
            patterns.append(PatternMatch(
                name="selling_pressure",
                description="Heavy selling pressure detected",
                score_impact=-20,
                confidence=0.85,
                details={"buys": buys, "sells": sells, "ratio": buy_sell_ratio},
            ))

        # High transaction count (active trading)
        if total_txns > 500:
            patterns.append(PatternMatch(
                name="high_activity",
                description=f"High trading activity: {total_txns} transactions in 24h",
                score_impact=15,
                confidence=0.9,
                details={"total_txns": total_txns},
            ))

        # Low activity warning
        if total_txns < 20:
            patterns.append(PatternMatch(
                name="low_activity_warning",
                description="Very low trading activity",
                score_impact=-10,
                confidence=0.8,
                details={"total_txns": total_txns},
            ))

        return patterns

    def _analyze_age_patterns(
        self,
        token_data: Dict[str, Any],
    ) -> List[PatternMatch]:
        """Analyze token age patterns."""
        patterns = []

        age_hours = token_data.get("age_hours")

        if age_hours is None:
            return patterns

        # Fresh token (high potential, high risk)
        if age_hours <= self.thresholds["fresh_token_max_age"]:
            patterns.append(PatternMatch(
                name="fresh_token",
                description=f"Fresh token: {age_hours:.1f} hours old",
                score_impact=10,
                confidence=0.7,
                details={"age_hours": age_hours},
            ))

        # New token sweet spot (survived initial dump risk)
        elif age_hours <= self.thresholds["new_token_max_age"]:
            patterns.append(PatternMatch(
                name="new_token",
                description=f"New token in sweet spot: {age_hours:.1f} hours old",
                score_impact=15,
                confidence=0.8,
                details={"age_hours": age_hours},
            ))

        # Established token
        elif age_hours > 168:  # > 1 week
            patterns.append(PatternMatch(
                name="established_token",
                description="Established token (> 1 week old)",
                score_impact=5,
                confidence=0.9,
                details={"age_hours": age_hours},
            ))

        return patterns

    def _analyze_market_cap_patterns(
        self,
        token_data: Dict[str, Any],
    ) -> List[PatternMatch]:
        """Analyze market cap patterns."""
        patterns = []

        market_cap = token_data.get("market_cap", 0)
        fdv = token_data.get("fdv", 0)

        # Micro cap (highest potential, highest risk)
        if 0 < market_cap < self.thresholds["micro_cap_max"]:
            patterns.append(PatternMatch(
                name="micro_cap",
                description=f"Micro cap: ${market_cap:,.0f}",
                score_impact=10,
                confidence=0.7,
                details={"market_cap": market_cap},
            ))

        # Small cap sweet spot
        elif market_cap < self.thresholds["small_cap_max"]:
            patterns.append(PatternMatch(
                name="small_cap",
                description=f"Small cap opportunity: ${market_cap:,.0f}",
                score_impact=15,
                confidence=0.8,
                details={"market_cap": market_cap},
            ))

        # Mid cap (less upside but more stable)
        elif market_cap < self.thresholds["mid_cap_max"]:
            patterns.append(PatternMatch(
                name="mid_cap",
                description=f"Mid cap: ${market_cap:,.0f}",
                score_impact=5,
                confidence=0.85,
                details={"market_cap": market_cap},
            ))

        return patterns

    def _analyze_name_patterns(
        self,
        token_data: Dict[str, Any],
    ) -> List[PatternMatch]:
        """Analyze token name/symbol for bullish or bearish keywords."""
        patterns = []

        name = (token_data.get("token_name") or "").lower()
        symbol = (token_data.get("token_symbol") or "").lower()
        combined = f"{name} {symbol}"

        # Check for bullish keywords (AI/tech themes perform well on Bags.fm)
        bullish_matches = []
        for keyword in BULLISH_KEYWORDS:
            if keyword in combined:
                bullish_matches.append(keyword)

        if len(bullish_matches) >= 2:
            patterns.append(PatternMatch(
                name="strong_theme",
                description=f"Strong AI/tech theme: matches {', '.join(bullish_matches[:3])}",
                score_impact=20,
                confidence=0.75,
                details={"matches": bullish_matches},
            ))
        elif bullish_matches:
            patterns.append(PatternMatch(
                name="bullish_theme",
                description=f"Bullish theme detected: {bullish_matches[0]}",
                score_impact=10,
                confidence=0.7,
                details={"matches": bullish_matches},
            ))

        # Check for bearish keywords
        for keyword in BEARISH_KEYWORDS:
            if keyword in combined:
                patterns.append(PatternMatch(
                    name="bearish_keyword",
                    description=f"Warning keyword detected: {keyword}",
                    score_impact=-30,
                    confidence=0.9,
                    details={"keyword": keyword},
                ))
                break

        return patterns

    def _analyze_bags_patterns(
        self,
        bags_data: Dict[str, Any],
    ) -> List[PatternMatch]:
        """Analyze Bags.fm specific patterns."""
        patterns = []

        # Verified Bags.fm token
        patterns.append(PatternMatch(
            name="bags_verified",
            description="Verified Bags.fm launched token",
            score_impact=15,
            confidence=1.0,
            details={"is_bags_token": True},
        ))

        # Analyze creator fees (high fees = successful token)
        lifetime_fees = bags_data.get("lifetime_fees")
        if lifetime_fees:
            total_fees = lifetime_fees.get("total", 0)

            if total_fees > 100000:  # > $100k
                patterns.append(PatternMatch(
                    name="high_creator_earnings",
                    description=f"High creator earnings: ${total_fees:,.0f}",
                    score_impact=25,
                    confidence=0.9,
                    details={"total_fees": total_fees},
                ))
            elif total_fees > 10000:  # > $10k
                patterns.append(PatternMatch(
                    name="good_creator_earnings",
                    description=f"Good creator earnings: ${total_fees:,.0f}",
                    score_impact=15,
                    confidence=0.85,
                    details={"total_fees": total_fees},
                ))

        return patterns

    def get_pattern_summary(
        self,
        patterns: List[PatternMatch],
    ) -> Dict[str, Any]:
        """
        Generate a summary of detected patterns.

        Args:
            patterns: List of detected patterns

        Returns:
            Summary with counts, total score impact, etc.
        """
        bullish = [p for p in patterns if p.score_impact > 0]
        bearish = [p for p in patterns if p.score_impact < 0]
        neutral = [p for p in patterns if p.score_impact == 0]

        total_positive = sum(p.score_impact for p in bullish)
        total_negative = sum(p.score_impact for p in bearish)

        return {
            "total_patterns": len(patterns),
            "bullish_count": len(bullish),
            "bearish_count": len(bearish),
            "neutral_count": len(neutral),
            "total_positive_impact": total_positive,
            "total_negative_impact": total_negative,
            "net_impact": total_positive + total_negative,
            "bullish_patterns": [p.name for p in bullish],
            "bearish_patterns": [p.name for p in bearish],
            "top_pattern": max(patterns, key=lambda p: abs(p.score_impact)).name if patterns else None,
        }
