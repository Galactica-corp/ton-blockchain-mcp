"""
TONAPI v2 client.
Wraps all working TONAPI v2 endpoints. No stubs — every method hits a real endpoint.
"""
import aiohttp
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class TonClient:
    def __init__(self, api_key: str, base_url: str = "https://tonapi.io"):
        self.api_key = api_key
        self.base_url = base_url.strip().rstrip('/')
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session

    async def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        try:
            async with session.request(method, url, params=params, json=data, timeout=aiohttp.ClientTimeout(total=60)) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Error making request to {url}: {e}")
            raise

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # =====================================================================
    # ACCOUNTS
    # =====================================================================

    async def get_account_info(self, address: str) -> Dict:
        """GET /v2/accounts/{account_id}: Account info (balance, status, interfaces)."""
        return await self._make_request("GET", f"/v2/accounts/{address}")

    async def get_account_transactions(
        self, address: str, limit: int = 100,
        after_lt: int = None, before_lt: int = None,
        sort_order: str = None, start_date: int = None, end_date: int = None
    ) -> Dict:
        """GET /v2/accounts/{account_id}/events: Account events with pagination.
        Max limit=100 per page. Use next_from as before_lt for next page.
        """
        params = {"limit": min(limit, 100)}
        if after_lt is not None:
            params["after_lt"] = after_lt
        if before_lt is not None:
            params["before_lt"] = before_lt
        if sort_order is not None:
            params["sort_order"] = sort_order
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        return await self._make_request("GET", f"/v2/accounts/{address}/events", params=params)

    async def get_accounts_bulk(self, addresses: List[str]) -> Dict:
        """POST /v2/accounts/_bulk: Get info for multiple accounts."""
        data = {"account_ids": addresses}
        return await self._make_request("POST", "/v2/accounts/_bulk", data=data)

    async def search_accounts(self, name: str) -> Dict:
        """GET /v2/accounts/search: Search accounts by domain name."""
        params = {"name": name}
        return await self._make_request("GET", "/v2/accounts/search", params=params)

    async def get_account_diff(self, address: str, start_date: int, end_date: int) -> Dict:
        """GET /v2/accounts/{account_id}/diff: Balance change over time period."""
        params = {"start_date": start_date, "end_date": end_date}
        return await self._make_request("GET", f"/v2/accounts/{address}/diff", params=params)

    async def account_dns_backresolve(self, address: str) -> Dict:
        """GET /v2/accounts/{account_id}/dns/backresolve: Reverse DNS lookup."""
        return await self._make_request("GET", f"/v2/accounts/{address}/dns/backresolve")

    async def get_account_public_key(self, address: str) -> Dict:
        """GET /v2/accounts/{account_id}/publickey: Get public key."""
        return await self._make_request("GET", f"/v2/accounts/{address}/publickey")

    async def get_account_subscriptions(self, address: str) -> Dict:
        """GET /v2/accounts/{account_id}/subscriptions: Get subscriptions."""
        return await self._make_request("GET", f"/v2/accounts/{address}/subscriptions")

    async def get_account_traces(self, address: str, limit: int = 100) -> Dict:
        """GET /v2/accounts/{account_id}/traces: Get traces for account."""
        params = {"limit": limit}
        return await self._make_request("GET", f"/v2/accounts/{address}/traces", params=params)

    async def get_account_event(self, address: str, event_id: str) -> Dict:
        """GET /v2/accounts/{account_id}/events/{event_id}: Specific event for account."""
        return await self._make_request("GET", f"/v2/accounts/{address}/events/{event_id}")

    # =====================================================================
    # JETTONS
    # =====================================================================

    async def get_jetton_balances(self, address: str, currencies: Optional[List[str]] = None) -> Dict:
        """GET /v2/accounts/{account_id}/jettons: All jetton balances for address.
        Pass currencies=['usd'] to include price data.
        """
        params = {}
        if currencies:
            params["currencies"] = ",".join(currencies)
        return await self._make_request("GET", f"/v2/accounts/{address}/jettons", params=params)

    async def get_jetton_balance(self, address: str, jetton_id: str, currencies: Optional[List[str]] = None) -> Dict:
        """GET /v2/accounts/{account_id}/jettons/{jetton_id}: Specific jetton balance."""
        params = {}
        if currencies:
            params["currencies"] = ",".join(currencies)
        return await self._make_request("GET", f"/v2/accounts/{address}/jettons/{jetton_id}", params=params)

    async def get_account_jettons_history(self, address: str, limit: int = 100, before_lt: Optional[int] = None) -> Dict:
        """GET /v2/accounts/{account_id}/jettons/history: Jetton transfer history (all jettons)."""
        params = {"limit": min(limit, 1000)}
        if before_lt:
            params["before_lt"] = before_lt
        return await self._make_request("GET", f"/v2/accounts/{address}/jettons/history", params=params)

    async def get_account_jetton_history_by_id(self, address: str, jetton_id: str, limit: int = 100, before_lt: Optional[int] = None) -> Dict:
        """GET /v2/accounts/{account_id}/jettons/{jetton_id}/history: Transfer history for specific jetton."""
        params = {"limit": min(limit, 1000)}
        if before_lt:
            params["before_lt"] = before_lt
        return await self._make_request("GET", f"/v2/accounts/{address}/jettons/{jetton_id}/history", params=params)

    async def get_jettons(self, limit: int = 100, offset: int = 0) -> Dict:
        """GET /v2/jettons: List indexed jettons (max 1000)."""
        params = {"limit": min(limit, 1000), "offset": offset}
        return await self._make_request("GET", "/v2/jettons", params=params)

    async def get_jetton_info(self, jetton_id: str) -> Dict:
        """GET /v2/jettons/{account_id}: Jetton metadata (name, symbol, holders, supply, verification)."""
        return await self._make_request("GET", f"/v2/jettons/{jetton_id}")

    async def get_jetton_infos_bulk(self, jetton_ids: List[str]) -> Dict:
        """POST /v2/jettons/_bulk: Bulk jetton metadata."""
        data = {"account_ids": jetton_ids}
        return await self._make_request("POST", "/v2/jettons/_bulk", data=data)

    async def get_jetton_holders(self, jetton_id: str, limit: int = 100, offset: int = 0) -> Dict:
        """GET /v2/jettons/{account_id}/holders: Top holders (max 1000, offset max 9000)."""
        params = {"limit": min(limit, 1000), "offset": min(offset, 9000)}
        return await self._make_request("GET", f"/v2/jettons/{jetton_id}/holders", params=params)

    # =====================================================================
    # NFT
    # =====================================================================

    async def get_account_nfts(self, address: str) -> Dict:
        """GET /v2/accounts/{account_id}/nfts: All NFTs owned by address."""
        return await self._make_request("GET", f"/v2/accounts/{address}/nfts")

    async def get_account_nft_history(self, address: str, limit: int = 100) -> Dict:
        """GET /v2/accounts/{account_id}/nfts/history: NFT transfer history."""
        params = {"limit": limit}
        return await self._make_request("GET", f"/v2/accounts/{address}/nfts/history", params=params)

    async def get_nft_collection(self, collection_address: str) -> Dict:
        """GET /v2/nfts/collections/{account_id}: NFT collection info."""
        return await self._make_request("GET", f"/v2/nfts/collections/{collection_address}")

    async def get_nft_collection_items(self, collection_address: str) -> Dict:
        """GET /v2/nfts/collections/{account_id}/items: Items in collection."""
        return await self._make_request("GET", f"/v2/nfts/collections/{collection_address}/items")

    async def get_nft_item(self, nft_address: str) -> Dict:
        """GET /v2/nfts/{account_id}: Single NFT item info."""
        return await self._make_request("GET", f"/v2/nfts/{nft_address}")

    async def get_nft_history_by_id(self, nft_address: str) -> Dict:
        """GET /v2/nfts/{account_id}/history: NFT transfer history."""
        return await self._make_request("GET", f"/v2/nfts/{nft_address}/history")

    async def get_nft_collections(self, limit: int = 100) -> Dict:
        """GET /v2/nfts/collections: List NFT collections."""
        params = {"limit": limit}
        return await self._make_request("GET", "/v2/nfts/collections", params=params)

    async def get_nft_items_bulk(self, addresses: List[str]) -> Dict:
        """POST /v2/nfts/_bulk: Bulk NFT item lookup."""
        data = {"account_ids": addresses}
        return await self._make_request("POST", "/v2/nfts/_bulk", data=data)

    # =====================================================================
    # EVENTS & TRACES
    # =====================================================================

    async def get_event(self, event_id: str) -> Dict:
        """GET /v2/events/{event_id}: High-level event with parsed actions.
        Accepts event ID or tx hash (hex without 0x, or base64url).
        Returns actions like JettonTransfer, JettonSwap, NftPurchase, etc.
        """
        return await self._make_request("GET", f"/v2/events/{event_id}")

    async def get_event_jettons(self, event_id: str) -> Dict:
        """GET /v2/events/{event_id}/jettons: Jetton-specific view of an event."""
        return await self._make_request("GET", f"/v2/events/{event_id}/jettons")

    async def get_trace(self, trace_id: str) -> Dict:
        """GET /v2/traces/{trace_id}: Full execution trace."""
        return await self._make_request("GET", f"/v2/traces/{trace_id}")

    # =====================================================================
    # BLOCKCHAIN (low-level)
    # =====================================================================

    async def get_transaction(self, tx_hash: str) -> Dict:
        """GET /v2/blockchain/transactions/{transaction_id}: Raw transaction data."""
        return await self._make_request("GET", f"/v2/blockchain/transactions/{tx_hash}")

    async def get_blockchain_transaction_by_message_hash(self, msg_id: str) -> Dict:
        """GET /v2/blockchain/messages/{msg_id}/transaction: Transaction by message hash."""
        return await self._make_request("GET", f"/v2/blockchain/messages/{msg_id}/transaction")

    async def get_blockchain_masterchain_head(self) -> Dict:
        """GET /v2/blockchain/masterchain-head: Latest masterchain block."""
        return await self._make_request("GET", "/v2/blockchain/masterchain-head")

    async def get_blockchain_validators(self) -> Dict:
        """GET /v2/blockchain/validators: Current validators."""
        return await self._make_request("GET", "/v2/blockchain/validators")

    async def get_blockchain_block(self, block_id: str) -> Dict:
        """GET /v2/blockchain/blocks/{block_id}: Block data."""
        return await self._make_request("GET", f"/v2/blockchain/blocks/{block_id}")

    async def get_blockchain_block_transactions(self, block_id: str, limit: int = 100) -> Dict:
        """GET /v2/blockchain/blocks/{block_id}/transactions: Block transactions."""
        params = {"limit": limit}
        return await self._make_request("GET", f"/v2/blockchain/blocks/{block_id}/transactions", params=params)

    async def get_blockchain_account_transactions(self, address: str, limit: int = 100) -> Dict:
        """GET /v2/blockchain/accounts/{account_id}/transactions: Raw account transactions."""
        params = {"limit": min(limit, 1000)}
        return await self._make_request("GET", f"/v2/blockchain/accounts/{address}/transactions", params=params)

    async def get_blockchain_raw_account(self, address: str) -> Dict:
        """GET /v2/blockchain/accounts/{account_id}: Raw blockchain account data."""
        return await self._make_request("GET", f"/v2/blockchain/accounts/{address}")

    async def get_blockchain_config(self) -> Dict:
        """GET /v2/blockchain/config: Blockchain config params."""
        return await self._make_request("GET", "/v2/blockchain/config")

    async def blockchain_account_inspect(self, address: str) -> Dict:
        """GET /v2/blockchain/accounts/{account_id}/inspect: Inspect account."""
        return await self._make_request("GET", f"/v2/blockchain/accounts/{address}/inspect")

    # =====================================================================
    # DNS
    # =====================================================================

    async def resolve_dns(self, domain: str) -> Dict:
        """GET /v2/dns/{domain_name}/resolve: Resolve .ton domain to address."""
        return await self._make_request("GET", f"/v2/dns/{domain}/resolve")

    async def get_dns_info(self, domain: str) -> Dict:
        """GET /v2/dns/{domain_name}: Get domain info."""
        return await self._make_request("GET", f"/v2/dns/{domain}")

    # =====================================================================
    # STAKING
    # =====================================================================

    async def get_staking_pools(self, available_for: Optional[str] = None, include_unverified: bool = False) -> Dict:
        """GET /v2/staking/pools: List staking pools.
        available_for: filter pools available for this address.
        include_unverified: include unwhitelisted pools (may be risky).
        """
        params = {}
        if available_for:
            params["available_for"] = available_for
        if include_unverified:
            params["include_unverified"] = "true"
        return await self._make_request("GET", "/v2/staking/pools", params=params)

    async def get_staking_pool(self, pool_address: str) -> Dict:
        """GET /v2/staking/pool/{account_id}: Single staking pool info."""
        return await self._make_request("GET", f"/v2/staking/pool/{pool_address}")

    async def get_staking_pool_history(self, pool_address: str, limit: int = 100) -> Dict:
        """GET /v2/staking/pool/{account_id}/history: Pool APY history."""
        params = {"limit": limit}
        return await self._make_request("GET", f"/v2/staking/pool/{pool_address}/history", params=params)

    async def get_nominator_pools(self, address: str) -> Dict:
        """GET /v2/staking/nominator/{account_id}/pools: Pools where address participates."""
        return await self._make_request("GET", f"/v2/staking/nominator/{address}/pools")

    # =====================================================================
    # RATES (prices)
    # =====================================================================

    async def get_ton_price(self, currency: str = "usd") -> Dict:
        """Get TON price via /v2/rates with CoinGecko fallback."""
        params = {"tokens": "ton", "currencies": currency}
        data = await self._make_request("GET", "/v2/rates", params=params)
        ton_data = data.get("rates", {}).get("ton", {})
        prices = ton_data.get("prices", {})
        diffs = {
            "diff_24h": ton_data.get("diff_24h", {}).get("TON"),
            "diff_7d": ton_data.get("diff_7d", {}).get("TON"),
            "diff_30d": ton_data.get("diff_30d", {}).get("TON"),
        }
        price = prices.get(currency.upper())
        if price is not None:
            return {"price": price, **diffs, "source": "tonapi.io"}
        # Fallback to CoinGecko
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies={currency}"
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    cg_data = await resp.json()
                    cg_price = cg_data.get("the-open-network", {}).get(currency.lower())
                    if cg_price is not None:
                        logger.warning("TON price fallback: using CoinGecko price.")
                        return {"price": cg_price, "source": "coingecko"}
        except Exception as e:
            logger.error(f"TON price fallback failed: {e}")
        return {"price": None, **diffs, "source": "none"}

    async def get_jetton_price(self, tokens: List[str], currency: str = "usd") -> Dict:
        """Get jetton prices via /v2/rates. Filters out 'ton'."""
        tokens = [t for t in tokens if t.lower() != "ton"]
        if not tokens:
            return {}
        params = {"tokens": ",".join(tokens), "currencies": currency}
        data = await self._make_request("GET", "/v2/rates", params=params)
        rates = data.get("rates", {})
        result = {}
        for token, info in rates.items():
            prices = info.get("prices", {})
            diffs = {
                "diff_24h": info.get("diff_24h", {}).get(token.upper()),
                "diff_7d": info.get("diff_7d", {}).get(token.upper()),
                "diff_30d": info.get("diff_30d", {}).get(token.upper()),
            }
            result[token] = {"price": prices.get(currency.upper()), **diffs}
        return result

    # =====================================================================
    # ADDRESS PARSING
    # =====================================================================

    async def parse_address(self, address: str) -> Dict:
        """GET /v2/address/{account_id}/parse: Parse address into all formats."""
        return await self._make_request("GET", f"/v2/address/{address}/parse")
