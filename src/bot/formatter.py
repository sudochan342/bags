"""
Format alerts and messages for Telegram.
"""

from typing import Dict, Any, List
from ..analysis.scorer import TokenScore
from ..analysis.patterns import PatternMatch


class AlertFormatter:
    """Format token alerts for Telegram messages."""

    @staticmethod
    def format_discovery_alert(score: TokenScore) -> str:
        """
        Format a new token discovery alert.

        Args:
            score: TokenScore object

        Returns:
            Formatted Telegram message (Markdown)
        """
        # Grade emoji
        grade_emoji = {
            "A": "🅰️",
            "B": "🅱️",
            "C": "🆑",
            "D": "🆔",
            "F": "🆘",
        }.get(score.grade, "❓")

        # Alert level emoji
        level_emoji = {
            "high": "🚨",
            "medium": "⚠️",
            "low": "📊",
        }.get(score.alert_level, "📌")

        # Bags.fm badge
        bags_badge = "🎒 BAGS.FM" if score.is_bags_token else ""

        # Price change indicator
        change_emoji = "📈" if score.price_change_24h > 0 else "📉"
        change_sign = "+" if score.price_change_24h > 0 else ""

        # Build bullish patterns list
        bullish_patterns = [p for p in score.patterns if p.score_impact > 0]
        patterns_text = ""
        if bullish_patterns:
            top_patterns = sorted(bullish_patterns, key=lambda p: p.score_impact, reverse=True)[:3]
            patterns_text = "\n".join([f"  • {p.description}" for p in top_patterns])

        # Age text
        age_text = ""
        if score.age_hours is not None:
            if score.age_hours < 24:
                age_text = f"⏱ {score.age_hours:.1f}h old"
            else:
                age_text = f"⏱ {score.age_hours/24:.1f}d old"

        message = f"""
{level_emoji} *NEW TOKEN ALERT* {level_emoji}

{grade_emoji} *{score.token_name}* (${score.token_symbol}) {bags_badge}

📊 *Score: {score.total_score}/100* | Grade: {score.grade}

💰 *Price:* ${score.price_usd:.8f}
💎 *Market Cap:* ${score.market_cap:,.0f}
💧 *Liquidity:* ${score.liquidity_usd:,.0f}
📈 *24h Volume:* ${score.volume_24h:,.0f}
{change_emoji} *24h Change:* {change_sign}{score.price_change_24h:.1f}%
{age_text}

*Score Breakdown:*
  📊 Pattern: {score.pattern_score}/40
  💧 Liquidity: {score.liquidity_score}/20
  📈 Volume: {score.volume_score}/20
  🚀 Momentum: {score.momentum_score}/20
  ⚠️ Risk: {score.risk_score}

*Key Signals:*
{patterns_text if patterns_text else "  • No major signals detected"}

🔗 [DexScreener]({score.url})
📋 `{score.token_address}`
"""
        return message.strip()

    @staticmethod
    def format_volume_surge_alert(score: TokenScore) -> str:
        """Format a volume surge alert."""
        message = f"""
🔥 *VOLUME SURGE DETECTED* 🔥

*{score.token_name}* (${score.token_symbol})

📈 *24h Volume:* ${score.volume_24h:,.0f}
💧 *Liquidity:* ${score.liquidity_usd:,.0f}
📊 *Score:* {score.total_score}/100

🔗 [DexScreener]({score.url})
"""
        return message.strip()

    @staticmethod
    def format_momentum_alert(score: TokenScore) -> str:
        """Format a momentum alert."""
        change_sign = "+" if score.price_change_24h > 0 else ""

        message = f"""
🚀 *MOMENTUM ALERT* 🚀

*{score.token_name}* (${score.token_symbol})

💰 *Price:* ${score.price_usd:.8f}
📈 *24h Change:* {change_sign}{score.price_change_24h:.1f}%
📊 *Score:* {score.total_score}/100

🔗 [DexScreener]({score.url})
"""
        return message.strip()

    @staticmethod
    def format_daily_summary(
        scores: List[TokenScore],
        stats: Dict[str, Any],
    ) -> str:
        """Format daily summary message."""
        # Top tokens by score
        top_tokens = sorted(scores, key=lambda s: s.total_score, reverse=True)[:5]

        top_tokens_text = ""
        for i, token in enumerate(top_tokens, 1):
            bags_badge = "🎒" if token.is_bags_token else ""
            top_tokens_text += f"{i}. *{token.token_symbol}* {bags_badge} - Score: {token.total_score}\n"

        message = f"""
📊 *DAILY SUMMARY* 📊

📈 *Tokens Tracked:* {stats.get('total_tokens', 0)}
🎒 *Bags.fm Tokens:* {stats.get('bags_tokens', 0)}
🔔 *Alerts Sent:* {stats.get('alerts_sent', 0)}

*Top Performers:*
{top_tokens_text if top_tokens_text else "No high-scoring tokens today"}

_Stay alert for new opportunities!_
"""
        return message.strip()

    @staticmethod
    def format_error_message(error: str) -> str:
        """Format error notification."""
        return f"""
⚠️ *Bot Error* ⚠️

{error}

_The bot will continue monitoring._
"""

    @staticmethod
    def format_startup_message() -> str:
        """Format bot startup message."""
        return """
🤖 *Bags.fm Coin Detection Bot Started* 🤖

Monitoring for:
• New token launches
• Volume surges
• Momentum patterns
• High-potential opportunities

_Alerts will be sent when promising tokens are detected._
"""

    @staticmethod
    def format_help_message() -> str:
        """Format help/info message."""
        return """
*Bags.fm Coin Detection Bot* 🎒

*Commands:*
/start - Start the bot
/status - Check bot status
/stats - View tracking statistics
/top - Show top scoring tokens
/help - Show this message

*Alert Levels:*
🚨 High - Score 80+ or volume surge
⚠️ Medium - Score 70+
📊 Low - Score 60+

*Scoring:*
Tokens are scored 0-100 based on:
• Pattern detection (AI themes, volume, etc.)
• Liquidity depth
• Trading volume
• Price momentum
• Risk factors

_The bot automatically scans for new opportunities every 60 seconds._
"""
