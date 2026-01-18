"""
Bags.fm API client for fetching token launch and creator data.
"""

import asyncio
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import structlog

from ..config import BAGS_BASE_URL, BAGS_ENDPOINTS

logger = structlog.get_logger()


class BagsClient:
    """Client for interacting with the Bags.fm API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Bags.fm client.

        Args:
            api_key: Optional API key for enhanced access
        """
        self.base_url = BAGS_BASE_URL
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Accept": "application/json",
                "User-Agent": "BagsCoinDetectionBot/1.0",
            }
            if self.api_key:
                headers["x-api-key"] = self.api_key

            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Make a request to the Bags.fm API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response or None on error
        """
        client = await self._get_client()
        url = f"{self.base_url}{endpoint}"

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Bags API returns {success: bool, data: ...} format
            if isinstance(data, dict) and "success" in data:
                if data["success"]:
                    return data.get("data", data)
                else:
                    logger.warning(
                        "bags_api_error",
                        error=data.get("error", "Unknown error"),
                        url=url,
                    )
                    return None
            return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "bags_http_error",
                status_code=e.response.status_code,
                url=url,
            )
            return None
        except Exception as e:
            logger.error("bags_request_error", error=str(e), url=url)
            return None

    async def get_token_lifetime_fees(
        self,
        token_mint: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get lifetime fees data for a token.

        This is a key metric - high creator earnings indicate successful tokens.

        Args:
            token_mint: Token mint address

        Returns:
            Fee data including total fees earned
        """
        endpoint = BAGS_ENDPOINTS["lifetime_fees"]
        return await self._request(endpoint, params={"tokenMint": token_mint})

    async def get_creator_info(
        self,
        token_mint: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get creator information for a token.

        Args:
            token_mint: Token mint address

        Returns:
            Creator data
        """
        endpoint = BAGS_ENDPOINTS["creator_info"]
        return await self._request(endpoint, params={"tokenMint": token_mint})

    async def enrich_token_data(
        self,
        token_mint: str,
    ) -> Dict[str, Any]:
        """
        Fetch all available Bags.fm data for a token.

        Args:
            token_mint: Token mint address

        Returns:
            Combined token data from Bags.fm
        """
        result = {
            "token_mint": token_mint,
            "is_bags_token": False,
            "lifetime_fees": None,
            "creator_info": None,
        }

        # Fetch lifetime fees
        fees = await self.get_token_lifetime_fees(token_mint)
        if fees:
            result["is_bags_token"] = True
            result["lifetime_fees"] = fees

        # Fetch creator info
        creator = await self.get_creator_info(token_mint)
        if creator:
            result["is_bags_token"] = True
            result["creator_info"] = creator

        return result


class BagsTokenTracker:
    """
    Track and discover Bags.fm tokens.

    Since Bags.fm doesn't have a public endpoint for listing all tokens,
    we use DexScreener search and then validate against Bags API.
    """

    def __init__(
        self,
        bags_client: BagsClient,
    ):
        """
        Initialize the tracker.

        Args:
            bags_client: Bags.fm API client
        """
        self.bags_client = bags_client
        self._known_bags_tokens: Dict[str, Dict[str, Any]] = {}

    async def validate_bags_token(
        self,
        token_address: str,
    ) -> bool:
        """
        Check if a token was launched on Bags.fm.

        Args:
            token_address: Token address to check

        Returns:
            True if token is from Bags.fm
        """
        if token_address in self._known_bags_tokens:
            return True

        data = await self.bags_client.enrich_token_data(token_address)
        if data.get("is_bags_token"):
            self._known_bags_tokens[token_address] = data
            return True
        return False

    async def get_bags_token_data(
        self,
        token_address: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached or fetch Bags.fm data for a token.

        Args:
            token_address: Token address

        Returns:
            Bags token data or None
        """
        if token_address in self._known_bags_tokens:
            return self._known_bags_tokens[token_address]

        data = await self.bags_client.enrich_token_data(token_address)
        if data.get("is_bags_token"):
            self._known_bags_tokens[token_address] = data
            return data
        return None

    def get_known_tokens(self) -> List[str]:
        """Get list of known Bags.fm token addresses."""
        return list(self._known_bags_tokens.keys())
