"""
Configuration management for the Bags.fm Coin Detection Bot.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Configuration
    telegram_bot_token: str = Field(..., description="Telegram Bot API Token")
    telegram_chat_id: str = Field(..., description="Telegram Chat/Channel ID to send alerts")

    # Bags.fm API (optional)
    bags_api_key: Optional[str] = Field(None, description="Bags.fm API Key for enhanced data")

    # Alert Thresholds
    min_liquidity_usd: float = Field(5000, description="Minimum liquidity in USD")
    min_volume_24h: float = Field(10000, description="Minimum 24h volume in USD")
    min_holders: int = Field(50, description="Minimum number of holders")
    max_top_holder_percent: float = Field(20, description="Max percentage any single holder can have")
    min_score: int = Field(60, description="Minimum score (0-100) to trigger alert")

    # Scanning Intervals (seconds)
    scan_interval_new_pairs: int = Field(60, description="How often to check for new pairs")
    scan_interval_trending: int = Field(300, description="How often to check trending")
    scan_interval_pattern_check: int = Field(120, description="How often to run pattern analysis")

    # Database
    database_path: str = Field("./data/tokens.db", description="SQLite database path")

    # Logging
    log_level: str = Field("INFO", description="Logging level")

    # API Rate Limits
    dexscreener_rate_limit: int = Field(300, description="DexScreener requests per minute")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Get application settings, loading from .env if available."""
    return Settings()


# Pattern Detection Thresholds
PATTERN_THRESHOLDS = {
    # Volume patterns
    "volume_spike_multiplier": 2.0,  # Current volume > 2x average = spike
    "volume_surge_multiplier": 5.0,  # 5x = major surge

    # Liquidity patterns
    "healthy_liquidity_min": 10000,  # $10k minimum for healthy liquidity
    "strong_liquidity_min": 50000,   # $50k+ is strong

    # Price patterns
    "bullish_price_change_1h": 5,    # 5% in 1h is bullish
    "bullish_price_change_24h": 20,  # 20% in 24h is bullish

    # Holder patterns
    "min_healthy_holders": 100,
    "excellent_holder_count": 500,
    "max_whale_concentration": 15,   # No single holder > 15%

    # Age patterns (hours)
    "new_token_max_age": 72,         # 3 days = new
    "fresh_token_max_age": 24,       # 1 day = fresh

    # Market cap patterns
    "micro_cap_max": 100000,         # < $100k = micro
    "small_cap_max": 1000000,        # < $1M = small
    "mid_cap_max": 10000000,         # < $10M = mid
}

# Keywords that indicate promising AI/tech themed tokens (based on bags.fm success patterns)
BULLISH_KEYWORDS = [
    # AI/Tech themes (like GAS, RALPH, CMEM, VVM)
    "ai", "agent", "claude", "gpt", "llm", "neural", "machine", "learning",
    "vibe", "code", "dev", "hack", "build", "ship", "deploy",
    "gas", "compute", "gpu", "inference", "model", "memory",

    # Crypto native themes
    "sol", "solana", "degen", "alpha", "gem", "moon",

    # Viral/meme potential
    "pepe", "wojak", "chad", "based", "fren",
]

# Keywords that might indicate risky tokens
BEARISH_KEYWORDS = [
    "rug", "scam", "honeypot", "test", "fake", "copy",
]

# DexScreener API endpoints
DEXSCREENER_BASE_URL = "https://api.dexscreener.com"
DEXSCREENER_ENDPOINTS = {
    "search": "/latest/dex/search",
    "pairs": "/latest/dex/pairs/{chain_id}/{pair_address}",
    "tokens": "/tokens/v1/{chain_id}/{token_addresses}",
    "token_pairs": "/token-pairs/v1/{chain_id}/{token_address}",
    "boosted": "/token-boosts/latest/v1",
    "top_boosted": "/token-boosts/top/v1",
    "profiles": "/token-profiles/latest/v1",
}

# Bags.fm API endpoints
BAGS_BASE_URL = "https://public-api-v2.bags.fm/api/v1"
BAGS_ENDPOINTS = {
    "lifetime_fees": "/token-launch/lifetime-fees",
    "creator_info": "/token-launch/creator",
}

# Solana chain ID for DexScreener
SOLANA_CHAIN_ID = "solana"
