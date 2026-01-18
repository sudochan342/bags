"""
Main scanner that orchestrates token discovery and alerting.
"""

import asyncio
from typing import List, Set, Optional
from datetime import datetime, timedelta
import structlog

from .config import get_settings, Settings
from .api import DexScreenerClient, BagsClient
from .api.bags import BagsTokenTracker
from .analysis import PatternAnalyzer, TokenScorer
from .analysis.scorer import TokenScore
from .database import TokenTracker
from .bot import TelegramAlertBot
from .bot.telegram_bot import AlertManager

logger = structlog.get_logger()


class BagsCoinScanner:
    """
    Main scanner that discovers and analyzes tokens.

    Workflow:
    1. Scan for new/trending Solana tokens on DexScreener
    2. Check if tokens are from Bags.fm
    3. Analyze patterns and calculate scores
    4. Send alerts for high-scoring tokens
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the scanner.

        Args:
            settings: Application settings (loads from env if not provided)
        """
        self.settings = settings or get_settings()

        # Initialize clients
        self.dex_client = DexScreenerClient(
            rate_limit=self.settings.dexscreener_rate_limit
        )
        self.bags_client = BagsClient(api_key=self.settings.bags_api_key)
        self.bags_tracker = BagsTokenTracker(self.bags_client)

        # Initialize analysis
        self.pattern_analyzer = PatternAnalyzer()
        self.scorer = TokenScorer()

        # Initialize database
        self.db = TokenTracker(self.settings.database_path)

        # Initialize bot
        self.telegram_bot = TelegramAlertBot(
            token=self.settings.telegram_bot_token,
            chat_id=self.settings.telegram_chat_id,
        )
        self.alert_manager: Optional[AlertManager] = None

        # State
        self._running = False
        self._seen_tokens: Set[str] = set()
        self._last_scan: Optional[datetime] = None

    async def initialize(self):
        """Initialize all components."""
        logger.info("scanner_initializing")

        # Initialize database
        await self.db.initialize()

        # Load previously seen tokens
        known_tokens = await self.db.get_all_tracked_tokens()
        self._seen_tokens = set(known_tokens)
        logger.info("loaded_known_tokens", count=len(self._seen_tokens))

        # Initialize telegram bot
        await self.telegram_bot.initialize()
        self.alert_manager = AlertManager(self.telegram_bot)

        logger.info("scanner_initialized")

    async def shutdown(self):
        """Shutdown all components."""
        logger.info("scanner_shutting_down")
        self._running = False

        await self.dex_client.close()
        await self.bags_client.close()
        await self.db.close()
        await self.telegram_bot.stop()

        logger.info("scanner_shutdown_complete")

    async def run(self):
        """
        Main run loop.

        Continuously scans for tokens and sends alerts.
        """
        self._running = True

        # Send startup message
        await self.telegram_bot.send_startup_message()

        # Start alert processor
        alert_task = asyncio.create_task(self.alert_manager.process_queue())

        try:
            while self._running:
                try:
                    await self._scan_cycle()
                except Exception as e:
                    logger.error("scan_cycle_error", error=str(e))
                    await self.telegram_bot.send_error_notification(
                        f"Scan error: {str(e)[:100]}"
                    )

                # Wait for next scan
                await asyncio.sleep(self.settings.scan_interval_new_pairs)

        except asyncio.CancelledError:
            logger.info("scanner_cancelled")
        finally:
            self.alert_manager.stop()
            alert_task.cancel()
            try:
                await alert_task
            except asyncio.CancelledError:
                pass

    async def _scan_cycle(self):
        """Run a single scan cycle."""
        logger.info("scan_cycle_starting")
        self._last_scan = datetime.now()

        # 1. Get boosted/trending tokens from DexScreener
        tokens_to_analyze = []

        # Get boosted tokens
        boosted = await self.dex_client.get_boosted_tokens()
        for token in boosted:
            if token.get("chainId") == "solana":
                token_address = token.get("tokenAddress")
                if token_address:
                    pairs = await self.dex_client.get_token_pairs(token_address)
                    if pairs:
                        tokens_to_analyze.extend(pairs)
                    await asyncio.sleep(0.1)

        # Get top boosted tokens
        top_boosted = await self.dex_client.get_top_boosted_tokens()
        for token in top_boosted:
            if token.get("chainId") == "solana":
                token_address = token.get("tokenAddress")
                if token_address:
                    pairs = await self.dex_client.get_token_pairs(token_address)
                    if pairs:
                        tokens_to_analyze.extend(pairs)
                    await asyncio.sleep(0.1)

        # Search for bags-related tokens
        bags_pairs = await self.dex_client.search_bags_tokens()
        tokens_to_analyze.extend(bags_pairs)

        # Search for AI-themed tokens (common pattern on bags.fm)
        ai_searches = ["ai agent", "claude", "gpt", "vibe", "gas town"]
        for query in ai_searches:
            results = await self.dex_client.search_pairs(query)
            # Filter to Solana only
            solana_results = [p for p in results if p.get("chainId") == "solana"]
            tokens_to_analyze.extend(solana_results)
            await asyncio.sleep(0.2)

        logger.info("tokens_found", count=len(tokens_to_analyze))

        # Deduplicate
        unique_pairs = {}
        for pair in tokens_to_analyze:
            pair_addr = pair.get("pairAddress")
            if pair_addr and pair_addr not in unique_pairs:
                unique_pairs[pair_addr] = pair

        logger.info("unique_pairs", count=len(unique_pairs))

        # 2. Analyze each token
        high_score_tokens: List[TokenScore] = []

        for pair_addr, pair_data in unique_pairs.items():
            try:
                score = await self._analyze_token(pair_data)
                if score and score.alert_level != "none":
                    high_score_tokens.append(score)
            except Exception as e:
                logger.warning("token_analysis_error", pair=pair_addr, error=str(e))

        logger.info("high_score_tokens", count=len(high_score_tokens))

        # 3. Send alerts for qualifying tokens
        for score in high_score_tokens:
            # Check if we should alert (cooldown)
            should_alert = await self.db.should_send_alert(
                score.token_address,
                "discovery",
                cooldown_hours=4,
            )

            if should_alert:
                # Determine alert type based on patterns
                has_volume_surge = any(
                    p.name == "volume_surge" for p in score.patterns
                )

                if has_volume_surge:
                    await self.alert_manager.queue_alert(score, "volume_surge")
                elif score.alert_level == "high":
                    await self.alert_manager.queue_alert(score, "discovery")
                elif score.momentum_score >= 15:
                    await self.alert_manager.queue_alert(score, "momentum")
                else:
                    await self.alert_manager.queue_alert(score, "discovery")

                # Record alert in database
                await self.db.add_alert(
                    token_address=score.token_address,
                    alert_type="discovery",
                    alert_level=score.alert_level,
                    score=score.total_score,
                    message=f"Score: {score.total_score}, Grade: {score.grade}",
                )

        logger.info("scan_cycle_complete")

    async def _analyze_token(
        self,
        pair_data: dict,
    ) -> Optional[TokenScore]:
        """
        Analyze a single token.

        Args:
            pair_data: Raw pair data from DexScreener

        Returns:
            TokenScore or None if doesn't meet criteria
        """
        # Parse pair data
        token_data = self.dex_client.parse_pair_data(pair_data)

        token_address = token_data.get("token_address")
        if not token_address:
            return None

        # Apply basic filters
        if token_data.get("liquidity_usd", 0) < self.settings.min_liquidity_usd:
            return None
        if token_data.get("volume_h24", 0) < self.settings.min_volume_24h:
            return None

        # Check if Bags.fm token
        bags_data = None
        if token_address not in self._seen_tokens:
            bags_data = await self.bags_tracker.get_bags_token_data(token_address)
            await asyncio.sleep(0.1)

        # Calculate score
        score = self.scorer.score_token(token_data, bags_data)

        # Track token
        is_new = await self.db.add_or_update_token(
            token_address=score.token_address,
            token_name=score.token_name,
            token_symbol=score.token_symbol,
            pair_address=score.pair_address,
            price=score.price_usd,
            market_cap=score.market_cap,
            liquidity=score.liquidity_usd,
            is_bags_token=score.is_bags_token,
            data={"last_score": score.total_score},
        )

        if is_new:
            self._seen_tokens.add(token_address)
            logger.info(
                "new_token_discovered",
                symbol=score.token_symbol,
                score=score.total_score,
                is_bags=score.is_bags_token,
            )

        # Record score history
        await self.db.record_score(
            token_address=score.token_address,
            total_score=score.total_score,
            pattern_score=score.pattern_score,
            liquidity_score=score.liquidity_score,
            volume_score=score.volume_score,
            momentum_score=score.momentum_score,
            risk_score=score.risk_score,
            patterns=[{"name": p.name, "impact": p.score_impact} for p in score.patterns],
        )

        # Record price
        await self.db.record_price(
            token_address=score.token_address,
            price=score.price_usd,
            market_cap=score.market_cap,
            liquidity=score.liquidity_usd,
            volume_24h=score.volume_24h,
        )

        return score

    async def scan_once(self) -> List[TokenScore]:
        """
        Run a single scan and return results (for testing).

        Returns:
            List of high-scoring tokens
        """
        await self._scan_cycle()
        # Return recent high scores from database
        # For now, just return empty list - implement if needed
        return []
