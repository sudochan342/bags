"""
Telegram bot for sending alerts and handling commands.
"""

import asyncio
from typing import Optional, List
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
import structlog

from ..analysis.scorer import TokenScore
from .formatter import AlertFormatter

logger = structlog.get_logger()


class TelegramAlertBot:
    """
    Telegram bot for sending coin alerts.

    Supports both direct messages and channel posts.
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
    ):
        """
        Initialize the Telegram bot.

        Args:
            token: Telegram Bot API token
            chat_id: Chat/Channel ID to send alerts to
        """
        self.token = token
        self.chat_id = chat_id
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.formatter = AlertFormatter()
        self._running = False

    async def initialize(self):
        """Initialize the bot and set up command handlers."""
        self.bot = Bot(token=self.token)
        self.app = Application.builder().token(self.token).build()

        # Add command handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("status", self._cmd_status))

        logger.info("telegram_bot_initialized")

    async def start(self):
        """Start the bot (for command handling)."""
        if self.app:
            await self.app.initialize()
            await self.app.start()
            self._running = True
            logger.info("telegram_bot_started")

    async def stop(self):
        """Stop the bot."""
        if self.app:
            self._running = False
            await self.app.stop()
            await self.app.shutdown()
            logger.info("telegram_bot_stopped")

    async def send_message(
        self,
        text: str,
        parse_mode: str = ParseMode.MARKDOWN,
        disable_notification: bool = False,
    ) -> bool:
        """
        Send a message to the configured chat.

        Args:
            text: Message text
            parse_mode: Parse mode (Markdown or HTML)
            disable_notification: Whether to send silently

        Returns:
            True if sent successfully
        """
        if not self.bot:
            logger.error("telegram_bot_not_initialized")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
                disable_web_page_preview=True,
            )
            logger.debug("telegram_message_sent", length=len(text))
            return True
        except Exception as e:
            logger.error("telegram_send_failed", error=str(e))
            return False

    async def send_discovery_alert(
        self,
        score: TokenScore,
    ) -> bool:
        """
        Send a new token discovery alert.

        Args:
            score: TokenScore for the discovered token

        Returns:
            True if sent successfully
        """
        message = self.formatter.format_discovery_alert(score)
        return await self.send_message(message)

    async def send_volume_surge_alert(
        self,
        score: TokenScore,
    ) -> bool:
        """Send a volume surge alert."""
        message = self.formatter.format_volume_surge_alert(score)
        return await self.send_message(message)

    async def send_momentum_alert(
        self,
        score: TokenScore,
    ) -> bool:
        """Send a momentum alert."""
        message = self.formatter.format_momentum_alert(score)
        return await self.send_message(message)

    async def send_startup_message(self) -> bool:
        """Send bot startup notification."""
        message = self.formatter.format_startup_message()
        return await self.send_message(message)

    async def send_error_notification(
        self,
        error: str,
    ) -> bool:
        """Send error notification."""
        message = self.formatter.format_error_message(error)
        return await self.send_message(message, disable_notification=True)

    async def send_daily_summary(
        self,
        scores: List[TokenScore],
        stats: dict,
    ) -> bool:
        """Send daily summary."""
        message = self.formatter.format_daily_summary(scores, stats)
        return await self.send_message(message)

    # Command handlers
    async def _cmd_start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle /start command."""
        await update.message.reply_text(
            self.formatter.format_startup_message(),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _cmd_help(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle /help command."""
        await update.message.reply_text(
            self.formatter.format_help_message(),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _cmd_status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle /status command."""
        status = "🟢 *Bot Status: Running*" if self._running else "🔴 *Bot Status: Stopped*"
        await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)


class AlertManager:
    """
    Manage alert sending with rate limiting and deduplication.
    """

    def __init__(
        self,
        bot: TelegramAlertBot,
        min_alert_interval: int = 60,  # seconds between alerts for same token
    ):
        """
        Initialize the alert manager.

        Args:
            bot: TelegramAlertBot instance
            min_alert_interval: Minimum seconds between alerts for same token
        """
        self.bot = bot
        self.min_interval = min_alert_interval
        self._last_alerts: dict = {}  # token_address -> timestamp
        self._alert_queue: asyncio.Queue = asyncio.Queue()
        self._processing = False

    async def queue_alert(
        self,
        score: TokenScore,
        alert_type: str = "discovery",
    ):
        """
        Queue an alert for sending.

        Args:
            score: TokenScore to alert on
            alert_type: Type of alert (discovery, volume_surge, momentum)
        """
        await self._alert_queue.put((score, alert_type))

    async def process_queue(self):
        """Process queued alerts with rate limiting."""
        self._processing = True

        while self._processing:
            try:
                # Wait for alert with timeout
                try:
                    score, alert_type = await asyncio.wait_for(
                        self._alert_queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue

                # Check rate limit
                token_addr = score.token_address
                last_alert = self._last_alerts.get(token_addr, 0)
                now = asyncio.get_event_loop().time()

                if now - last_alert < self.min_interval:
                    logger.debug(
                        "alert_rate_limited",
                        token=score.token_symbol,
                        seconds_until_allowed=self.min_interval - (now - last_alert),
                    )
                    continue

                # Send alert based on type
                success = False
                if alert_type == "discovery":
                    success = await self.bot.send_discovery_alert(score)
                elif alert_type == "volume_surge":
                    success = await self.bot.send_volume_surge_alert(score)
                elif alert_type == "momentum":
                    success = await self.bot.send_momentum_alert(score)

                if success:
                    self._last_alerts[token_addr] = now
                    logger.info(
                        "alert_sent",
                        token=score.token_symbol,
                        type=alert_type,
                        score=score.total_score,
                    )

                # Rate limit between alerts
                await asyncio.sleep(1)

            except Exception as e:
                logger.error("alert_processing_error", error=str(e))
                await asyncio.sleep(5)

    def stop(self):
        """Stop processing alerts."""
        self._processing = False
