"""
SQLite database for tracking tokens and alerts.
"""

import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import structlog

logger = structlog.get_logger()


class TokenTracker:
    """
    Track tokens, alerts, and historical data using SQLite.
    """

    def __init__(self, db_path: str = "./data/tokens.db"):
        """
        Initialize the tracker.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize database and create tables."""
        # Ensure the data directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)

        # Create tables
        await self._db.executescript("""
            -- Tokens table
            CREATE TABLE IF NOT EXISTS tokens (
                token_address TEXT PRIMARY KEY,
                token_name TEXT,
                token_symbol TEXT,
                pair_address TEXT,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_bags_token BOOLEAN DEFAULT 0,
                initial_price REAL,
                initial_market_cap REAL,
                initial_liquidity REAL,
                peak_price REAL,
                peak_market_cap REAL,
                data JSON
            );

            -- Alerts table
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT,
                alert_type TEXT,
                alert_level TEXT,
                score INTEGER,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_to_telegram BOOLEAN DEFAULT 0,
                FOREIGN KEY (token_address) REFERENCES tokens(token_address)
            );

            -- Price history table
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT,
                price_usd REAL,
                market_cap REAL,
                liquidity_usd REAL,
                volume_24h REAL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (token_address) REFERENCES tokens(token_address)
            );

            -- Scores history table
            CREATE TABLE IF NOT EXISTS score_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT,
                total_score INTEGER,
                pattern_score INTEGER,
                liquidity_score INTEGER,
                volume_score INTEGER,
                momentum_score INTEGER,
                risk_score INTEGER,
                patterns JSON,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (token_address) REFERENCES tokens(token_address)
            );

            -- Create indexes for faster queries
            CREATE INDEX IF NOT EXISTS idx_alerts_token ON alerts(token_address);
            CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);
            CREATE INDEX IF NOT EXISTS idx_price_history_token ON price_history(token_address);
            CREATE INDEX IF NOT EXISTS idx_score_history_token ON score_history(token_address);
        """)
        await self._db.commit()
        logger.info("database_initialized", db_path=self.db_path)

    async def close(self):
        """Close database connection."""
        if self._db:
            await self._db.close()

    async def add_or_update_token(
        self,
        token_address: str,
        token_name: str,
        token_symbol: str,
        pair_address: str,
        price: float,
        market_cap: float,
        liquidity: float,
        is_bags_token: bool = False,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a new token or update existing one.

        Args:
            token_address: Token contract address
            token_name: Token name
            token_symbol: Token symbol
            pair_address: Trading pair address
            price: Current price in USD
            market_cap: Current market cap
            liquidity: Current liquidity
            is_bags_token: Whether token is from Bags.fm
            data: Additional data to store

        Returns:
            True if new token was added, False if updated
        """
        # Check if token exists
        cursor = await self._db.execute(
            "SELECT token_address, peak_price, peak_market_cap FROM tokens WHERE token_address = ?",
            (token_address,)
        )
        existing = await cursor.fetchone()

        if existing:
            # Update existing token
            _, peak_price, peak_market_cap = existing
            new_peak_price = max(peak_price or 0, price)
            new_peak_market_cap = max(peak_market_cap or 0, market_cap)

            await self._db.execute("""
                UPDATE tokens SET
                    token_name = ?,
                    token_symbol = ?,
                    pair_address = ?,
                    last_updated_at = CURRENT_TIMESTAMP,
                    is_bags_token = ?,
                    peak_price = ?,
                    peak_market_cap = ?,
                    data = ?
                WHERE token_address = ?
            """, (
                token_name,
                token_symbol,
                pair_address,
                is_bags_token,
                new_peak_price,
                new_peak_market_cap,
                json.dumps(data) if data else None,
                token_address,
            ))
            await self._db.commit()
            return False
        else:
            # Insert new token
            await self._db.execute("""
                INSERT INTO tokens (
                    token_address, token_name, token_symbol, pair_address,
                    is_bags_token, initial_price, initial_market_cap, initial_liquidity,
                    peak_price, peak_market_cap, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                token_address,
                token_name,
                token_symbol,
                pair_address,
                is_bags_token,
                price,
                market_cap,
                liquidity,
                price,
                market_cap,
                json.dumps(data) if data else None,
            ))
            await self._db.commit()
            logger.info(
                "new_token_added",
                address=token_address,
                symbol=token_symbol,
                is_bags=is_bags_token,
            )
            return True

    async def record_price(
        self,
        token_address: str,
        price: float,
        market_cap: float,
        liquidity: float,
        volume_24h: float,
    ):
        """Record price history for a token."""
        await self._db.execute("""
            INSERT INTO price_history (
                token_address, price_usd, market_cap, liquidity_usd, volume_24h
            ) VALUES (?, ?, ?, ?, ?)
        """, (token_address, price, market_cap, liquidity, volume_24h))
        await self._db.commit()

    async def record_score(
        self,
        token_address: str,
        total_score: int,
        pattern_score: int,
        liquidity_score: int,
        volume_score: int,
        momentum_score: int,
        risk_score: int,
        patterns: List[Dict[str, Any]],
    ):
        """Record score history for a token."""
        await self._db.execute("""
            INSERT INTO score_history (
                token_address, total_score, pattern_score, liquidity_score,
                volume_score, momentum_score, risk_score, patterns
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            token_address,
            total_score,
            pattern_score,
            liquidity_score,
            volume_score,
            momentum_score,
            risk_score,
            json.dumps(patterns),
        ))
        await self._db.commit()

    async def add_alert(
        self,
        token_address: str,
        alert_type: str,
        alert_level: str,
        score: int,
        message: str,
    ) -> int:
        """
        Add a new alert.

        Returns:
            Alert ID
        """
        cursor = await self._db.execute("""
            INSERT INTO alerts (
                token_address, alert_type, alert_level, score, message
            ) VALUES (?, ?, ?, ?, ?)
        """, (token_address, alert_type, alert_level, score, message))
        await self._db.commit()
        return cursor.lastrowid

    async def mark_alert_sent(self, alert_id: int):
        """Mark an alert as sent to Telegram."""
        await self._db.execute(
            "UPDATE alerts SET sent_to_telegram = 1 WHERE id = ?",
            (alert_id,)
        )
        await self._db.commit()

    async def get_recent_alerts(
        self,
        token_address: str,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get recent alerts for a token."""
        cursor = await self._db.execute("""
            SELECT id, alert_type, alert_level, score, message, created_at
            FROM alerts
            WHERE token_address = ?
            AND created_at > datetime('now', ?)
            ORDER BY created_at DESC
        """, (token_address, f"-{hours} hours"))

        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "alert_type": row[1],
                "alert_level": row[2],
                "score": row[3],
                "message": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]

    async def should_send_alert(
        self,
        token_address: str,
        alert_type: str,
        cooldown_hours: int = 4,
    ) -> bool:
        """
        Check if we should send an alert (avoid spam).

        Args:
            token_address: Token address
            alert_type: Type of alert
            cooldown_hours: Minimum hours between same alerts

        Returns:
            True if alert should be sent
        """
        cursor = await self._db.execute("""
            SELECT COUNT(*) FROM alerts
            WHERE token_address = ?
            AND alert_type = ?
            AND created_at > datetime('now', ?)
        """, (token_address, alert_type, f"-{cooldown_hours} hours"))

        row = await cursor.fetchone()
        return row[0] == 0

    async def get_token(
        self,
        token_address: str,
    ) -> Optional[Dict[str, Any]]:
        """Get token data."""
        cursor = await self._db.execute(
            "SELECT * FROM tokens WHERE token_address = ?",
            (token_address,)
        )
        row = await cursor.fetchone()

        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    async def get_all_tracked_tokens(self) -> List[str]:
        """Get all tracked token addresses."""
        cursor = await self._db.execute(
            "SELECT token_address FROM tokens"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_top_performers(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get tokens with highest price increase from initial."""
        cursor = await self._db.execute("""
            SELECT
                token_address,
                token_symbol,
                token_name,
                initial_price,
                peak_price,
                (peak_price - initial_price) / initial_price * 100 as gain_percent
            FROM tokens
            WHERE initial_price > 0 AND peak_price > 0
            ORDER BY gain_percent DESC
            LIMIT ?
        """, (limit,))

        rows = await cursor.fetchall()
        return [
            {
                "token_address": row[0],
                "token_symbol": row[1],
                "token_name": row[2],
                "initial_price": row[3],
                "peak_price": row[4],
                "gain_percent": row[5],
            }
            for row in rows
        ]

    async def get_statistics(self) -> Dict[str, Any]:
        """Get overall tracking statistics."""
        stats = {}

        # Total tokens
        cursor = await self._db.execute("SELECT COUNT(*) FROM tokens")
        stats["total_tokens"] = (await cursor.fetchone())[0]

        # Bags tokens
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM tokens WHERE is_bags_token = 1"
        )
        stats["bags_tokens"] = (await cursor.fetchone())[0]

        # Total alerts
        cursor = await self._db.execute("SELECT COUNT(*) FROM alerts")
        stats["total_alerts"] = (await cursor.fetchone())[0]

        # Alerts sent
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM alerts WHERE sent_to_telegram = 1"
        )
        stats["alerts_sent"] = (await cursor.fetchone())[0]

        return stats
