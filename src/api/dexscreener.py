"""
DexScreener API client for fetching token and pair data.
"""

import asyncio
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import structlog

from ..config import (
    DEXSCREENER_BASE_URL,
    DEXSCREENER_ENDPOINTS,
    SOLANA_CHAIN_ID,
)

logger = structlog.get_logger()


class DexScreenerClient:
    """Client for interacting with the DexScreener API."""

    def __init__(self, rate_limit: int = 300):
        """
        Initialize the DexScreener client.

        Args:
            rate_limit: Maximum requests per minute (default 300)
        """
        self.base_url = DEXSCREENER_BASE_URL
        self.rate_limit = rate_limit
        self._request_times: List[datetime] = []
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "BagsCoinDetectionBot/1.0",
                },
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _rate_limit_check(self):
        """Ensure we don't exceed rate limits."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if t > minute_ago]

        # If we're at the limit, wait
        if len(self._request_times) >= self.rate_limit:
            wait_time = (self._request_times[0] - minute_ago).total_seconds()
            if wait_time > 0:
                logger.debug("rate_limit_wait", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)

        self._request_times.append(now)

    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Make a rate-limited request to the DexScreener API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response or None on error
        """
        await self._rate_limit_check()

        client = await self._get_client()
        url = f"{self.base_url}{endpoint}"

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "dexscreener_http_error",
                status_code=e.response.status_code,
                url=url,
            )
            return None
        except Exception as e:
            logger.error("dexscreener_request_error", error=str(e), url=url)
            return None

    async def search_pairs(
        self,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Search for pairs matching a query.

        Args:
            query: Search query (e.g., "bags", "SOL/USDC")

        Returns:
            List of matching pairs
        """
        endpoint = DEXSCREENER_ENDPOINTS["search"]
        result = await self._request(endpoint, params={"q": query})

        if result and "pairs" in result:
            return result["pairs"]
        return []

    async def get_token_pairs(
        self,
        token_address: str,
        chain_id: str = SOLANA_CHAIN_ID,
    ) -> List[Dict[str, Any]]:
        """
        Get all pairs for a specific token.

        Args:
            token_address: Token contract address
            chain_id: Blockchain ID (default: solana)

        Returns:
            List of pairs for the token
        """
        endpoint = DEXSCREENER_ENDPOINTS["token_pairs"].format(
            chain_id=chain_id,
            token_address=token_address,
        )
        result = await self._request(endpoint)

        if result and isinstance(result, list):
            return result
        elif result and "pairs" in result:
            return result["pairs"]
        return []

    async def get_tokens(
        self,
        token_addresses: List[str],
        chain_id: str = SOLANA_CHAIN_ID,
    ) -> List[Dict[str, Any]]:
        """
        Get data for multiple tokens (up to 30).

        Args:
            token_addresses: List of token addresses
            chain_id: Blockchain ID (default: solana)

        Returns:
            List of token data
        """
        # API supports max 30 addresses per request
        addresses = ",".join(token_addresses[:30])
        endpoint = DEXSCREENER_ENDPOINTS["tokens"].format(
            chain_id=chain_id,
            token_addresses=addresses,
        )
        result = await self._request(endpoint)

        if result and isinstance(result, list):
            return result
        return []

    async def get_pair(
        self,
        pair_address: str,
        chain_id: str = SOLANA_CHAIN_ID,
    ) -> Optional[Dict[str, Any]]:
        """
        Get data for a specific pair.

        Args:
            pair_address: Pair contract address
            chain_id: Blockchain ID (default: solana)

        Returns:
            Pair data or None
        """
        endpoint = DEXSCREENER_ENDPOINTS["pairs"].format(
            chain_id=chain_id,
            pair_address=pair_address,
        )
        result = await self._request(endpoint)

        if result and "pairs" in result and result["pairs"]:
            return result["pairs"][0]
        return None

    async def get_boosted_tokens(self) -> List[Dict[str, Any]]:
        """
        Get recently boosted tokens.

        Returns:
            List of boosted token data
        """
        endpoint = DEXSCREENER_ENDPOINTS["boosted"]
        result = await self._request(endpoint)
        return result if isinstance(result, list) else []

    async def get_top_boosted_tokens(self) -> List[Dict[str, Any]]:
        """
        Get tokens with most active boosts.

        Returns:
            List of top boosted token data
        """
        endpoint = DEXSCREENER_ENDPOINTS["top_boosted"]
        result = await self._request(endpoint)
        return result if isinstance(result, list) else []

    async def get_token_profiles(self) -> List[Dict[str, Any]]:
        """
        Get latest token profiles.

        Returns:
            List of token profile data
        """
        endpoint = DEXSCREENER_ENDPOINTS["profiles"]
        result = await self._request(endpoint)
        return result if isinstance(result, list) else []

    async def search_bags_tokens(self) -> List[Dict[str, Any]]:
        """
        Search for tokens related to Bags.fm.

        Returns:
            List of bags-related pairs
        """
        # Search for bags-related tokens
        results = []

        # Search multiple queries to find bags tokens
        queries = ["bags", "bagsfm", "bags.fm"]
        for query in queries:
            pairs = await self.search_pairs(query)
            results.extend(pairs)
            await asyncio.sleep(0.2)  # Small delay between searches

        # Deduplicate by pair address
        seen = set()
        unique_results = []
        for pair in results:
            pair_address = pair.get("pairAddress")
            if pair_address and pair_address not in seen:
                seen.add(pair_address)
                unique_results.append(pair)

        return unique_results

    async def get_new_solana_pairs(
        self,
        max_age_hours: int = 72,
    ) -> List[Dict[str, Any]]:
        """
        Get new Solana pairs created within the specified time window.

        This searches for recent pairs by looking at boosted and trending tokens.

        Args:
            max_age_hours: Maximum age of pairs to include

        Returns:
            List of new pairs
        """
        results = []

        # Get boosted tokens (often new/trending)
        boosted = await self.get_boosted_tokens()
        for token in boosted:
            if token.get("chainId") == SOLANA_CHAIN_ID:
                token_address = token.get("tokenAddress")
                if token_address:
                    pairs = await self.get_token_pairs(token_address)
                    results.extend(pairs)
                    await asyncio.sleep(0.1)

        # Filter by creation time
        cutoff_time = datetime.now().timestamp() * 1000 - (max_age_hours * 3600 * 1000)
        new_pairs = []

        for pair in results:
            created_at = pair.get("pairCreatedAt", 0)
            if created_at > cutoff_time:
                new_pairs.append(pair)

        return new_pairs

    def parse_pair_data(self, pair: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw pair data into a normalized format.

        Args:
            pair: Raw pair data from API

        Returns:
            Normalized pair data
        """
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        txns = pair.get("txns", {})
        volume = pair.get("volume", {})
        price_change = pair.get("priceChange", {})
        liquidity = pair.get("liquidity", {})

        # Calculate transaction counts
        txns_h24 = txns.get("h24", {})
        buys_24h = txns_h24.get("buys", 0)
        sells_24h = txns_h24.get("sells", 0)

        # Parse creation time
        created_at = pair.get("pairCreatedAt", 0)
        if created_at:
            created_datetime = datetime.fromtimestamp(created_at / 1000)
            age_hours = (datetime.now() - created_datetime).total_seconds() / 3600
        else:
            created_datetime = None
            age_hours = None

        return {
            # Token info
            "token_address": base_token.get("address"),
            "token_name": base_token.get("name"),
            "token_symbol": base_token.get("symbol"),

            # Pair info
            "pair_address": pair.get("pairAddress"),
            "dex_id": pair.get("dexId"),
            "chain_id": pair.get("chainId"),
            "url": pair.get("url"),

            # Quote token
            "quote_token": quote_token.get("symbol"),

            # Price data
            "price_usd": float(pair.get("priceUsd", 0) or 0),
            "price_native": float(pair.get("priceNative", 0) or 0),

            # Market metrics
            "market_cap": float(pair.get("marketCap", 0) or 0),
            "fdv": float(pair.get("fdv", 0) or 0),
            "liquidity_usd": float(liquidity.get("usd", 0) or 0),

            # Volume
            "volume_h1": float(volume.get("h1", 0) or 0),
            "volume_h6": float(volume.get("h6", 0) or 0),
            "volume_h24": float(volume.get("h24", 0) or 0),

            # Price changes
            "price_change_m5": float(price_change.get("m5", 0) or 0),
            "price_change_h1": float(price_change.get("h1", 0) or 0),
            "price_change_h6": float(price_change.get("h6", 0) or 0),
            "price_change_h24": float(price_change.get("h24", 0) or 0),

            # Transactions
            "buys_24h": buys_24h,
            "sells_24h": sells_24h,
            "total_txns_24h": buys_24h + sells_24h,
            "buy_sell_ratio": buys_24h / sells_24h if sells_24h > 0 else buys_24h,

            # Age
            "created_at": created_datetime,
            "age_hours": age_hours,

            # Raw data for additional analysis
            "raw": pair,
        }
