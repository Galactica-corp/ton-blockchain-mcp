"""
GeckoTerminal API client for TON network.
Free API (no auth), 30 requests/minute.
Provides trending pools, token market data, and DEX analytics.
"""
import aiohttp
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

GECKO_BASE_URL = "https://api.geckoterminal.com/api/v2"
TON_NETWORK = "ton"


class GeckoClient:
    """Async client for GeckoTerminal API (free, no auth required)."""

    def __init__(self, base_url: str = GECKO_BASE_URL):
        self.base_url = base_url.strip().rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"Accept": "application/json"}
            )
        return self.session

    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        try:
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"GeckoTerminal request error for {url}: {e}")
            raise

    # --- Pool endpoints ---

    async def get_trending_pools(self, include_tokens: bool = True) -> Dict:
        """Get trending pools on TON with optional token metadata.
        Returns up to 20 trending pools sorted by GeckoTerminal's trending algorithm.
        With include_tokens=True, response includes full token metadata in 'included' array.
        """
        params = {}
        if include_tokens:
            params["include"] = "base_token,quote_token"
        return await self._make_request(
            f"/networks/{TON_NETWORK}/trending_pools", params=params
        )

    async def get_top_pools(
        self, sort: str = "h24_volume_usd_desc", page: int = 1,
        include_tokens: bool = True
    ) -> Dict:
        """Get pools sorted by volume or other metrics.
        sort options: h24_volume_usd_desc, h24_tx_count_desc
        """
        params = {"sort": sort, "page": page}
        if include_tokens:
            params["include"] = "base_token,quote_token"
        return await self._make_request(
            f"/networks/{TON_NETWORK}/pools", params=params
        )

    async def get_new_pools(self, include_tokens: bool = True) -> Dict:
        """Get recently created pools on TON."""
        params = {}
        if include_tokens:
            params["include"] = "base_token,quote_token"
        return await self._make_request(
            f"/networks/{TON_NETWORK}/new_pools", params=params
        )

    # --- Token endpoints ---

    async def get_token_info(self, token_address: str) -> Dict:
        """Get detailed token info: price, volume, FDV, market cap, top pools.
        This is the richest per-token data source on GeckoTerminal.
        """
        return await self._make_request(
            f"/networks/{TON_NETWORK}/tokens/{token_address}"
        )

    async def get_tokens_multi(self, addresses: List[str]) -> Dict:
        """Get info for multiple tokens at once (comma-separated addresses)."""
        addresses_str = ",".join(addresses)
        return await self._make_request(
            f"/networks/{TON_NETWORK}/tokens/multi/{addresses_str}"
        )

    # --- Cleanup ---

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
