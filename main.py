#!/usr/bin/env python3
"""
Bags.fm Coin Detection Telegram Bot

A bot that monitors Solana tokens (especially those launched on Bags.fm),
analyzes them for promising patterns, and sends alerts to Telegram.

Usage:
    python main.py

Environment variables required:
    TELEGRAM_BOT_TOKEN - Your Telegram bot token
    TELEGRAM_CHAT_ID - Chat/channel ID to send alerts to

Optional:
    BAGS_API_KEY - Bags.fm API key for enhanced data
    See .env.example for all options
"""

import asyncio
import signal
import sys
from pathlib import Path

import structlog

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.scanner import BagsCoinScanner
from src.config import get_settings


def setup_logging():
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def main():
    """Main entry point."""
    setup_logging()
    logger = structlog.get_logger()

    logger.info("bags_coin_detection_bot_starting")

    # Load settings
    try:
        settings = get_settings()
    except Exception as e:
        logger.error("failed_to_load_settings", error=str(e))
        logger.error("please_check_env_file")
        sys.exit(1)

    # Create scanner
    scanner = BagsCoinScanner(settings)

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_shutdown(signum, frame):
        logger.info("shutdown_signal_received", signal=signum)
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        # Initialize
        await scanner.initialize()

        # Run scanner with shutdown check
        scanner_task = asyncio.create_task(scanner.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [scanner_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error("fatal_error", error=str(e))
        raise
    finally:
        await scanner.shutdown()
        logger.info("bags_coin_detection_bot_stopped")


if __name__ == "__main__":
    asyncio.run(main())
