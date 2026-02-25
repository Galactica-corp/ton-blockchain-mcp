"""
MCP Tool implementations for TON Blockchain explorer.
All tools are backed by real API endpoints (TONAPI v2 + GeckoTerminal).
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from .ton_client import TonClient
from .gecko_client import GeckoClient
from .utils import format_ton_amount, assert_full_address

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Symbols to skip when extracting tokens from pool pairs (native TON)
_SKIP_SYMBOLS = {"TON", "WTON", "jWTON", "Wrapped TON"}

# Max events per API page (TONAPI hard limit)
_PAGE_SIZE = 100


class TooManyEventsError(Exception):
    """Raised when a timeframe contains more events than the configured max."""
    pass


class ToolManager:
    def __init__(self, ton_client: TonClient, gecko_client: GeckoClient, max_events: int = 1000):
        self.ton_client = ton_client
        self.gecko_client = gecko_client
        self.max_events = max_events

    # =================================================================
    # 1. analyze_address
    # =================================================================

    async def analyze_address(self, address: str, deep_analysis: bool = False) -> Dict[str, Any]:
        """Analyze a TON address: balance, jetton holdings, NFTs, recent activity."""
        try:
            assert_full_address(address)

            account_info = await self.ton_client.get_account_info(address)
            jetton_balances = await self.ton_client.get_jetton_balances(address, currencies=["usd"])
            nfts = await self.ton_client.get_account_nfts(address)
            transactions = await self.ton_client.get_account_transactions(address, limit=50)

            # TON balance + USD value
            ton_balance = float(account_info.get("balance", 0)) / 1e9
            ton_price_data = await self.get_ton_price(currency="usd")
            ton_price = None
            ton_usd = 0
            if ton_price_data and ton_price_data.get("price"):
                try:
                    ton_price = float(ton_price_data["price"])
                    ton_usd = ton_balance * ton_price
                except Exception:
                    pass

            # Jetton holdings with USD values
            jettons = jetton_balances.get("balances", [])
            jetton_usd_total = 0
            jetton_usd_details = []
            for jetton in jettons:
                j_meta = jetton.get("jetton", {})
                symbol = j_meta.get("symbol", "Unknown")
                decimals = j_meta.get("decimals", 9)
                balance = float(jetton.get("balance", 0)) / (10 ** decimals)
                # Price from the currencies param
                price_info = jetton.get("price", {})
                price = 0
                if price_info:
                    price = float(price_info.get("prices", {}).get("USD", 0) or 0)
                usd_value = balance * price
                jetton_usd_total += usd_value
                jetton_usd_details.append({
                    "symbol": symbol,
                    "address": j_meta.get("address"),
                    "balance": balance,
                    "price_usd": price,
                    "usd_value": usd_value,
                    "verification": j_meta.get("verification"),
                })

            total_usd = ton_usd + jetton_usd_total

            # Recent events info
            events = transactions.get("events", [])
            has_more = transactions.get("next_from") is not None

            result = {
                "address": address,
                "status": account_info.get("status"),
                "interfaces": account_info.get("interfaces", []),
                "ton_balance": ton_balance,
                "ton_usd_value": ton_usd,
                "jetton_count": len(jettons),
                "jetton_usd_value": jetton_usd_total,
                "jetton_holdings": jetton_usd_details,
                "nft_count": len(nfts.get("nft_items", [])),
                "wallet_value_usd": total_usd,
                "recent_events": {
                    "count": len(events),
                    "has_more": has_more,
                },
            }

            if deep_analysis:
                tx_analysis = self._analyze_events(events)
                result["analysis"] = tx_analysis

            return result
        except ValueError as e:
            return {"error": f"Invalid address: {e}"}
        except Exception as e:
            logger.error(f"Error in analyze_address: {e}")
            return {"error": str(e)}

    # =================================================================
    # 2. get_transaction_details
    # =================================================================

    async def get_transaction_details(self, tx_hash: str) -> Dict[str, Any]:
        """Get high-level event details for a transaction hash."""
        try:
            # Use the events API for parsed high-level actions
            event = await self.ton_client.get_event(tx_hash)

            actions_summary = []
            for action in event.get("actions", []):
                action_type = action.get("type", "Unknown")
                status = action.get("status", "unknown")
                simple_preview = action.get("simple_preview", {})

                entry = {
                    "type": action_type,
                    "status": status,
                    "description": simple_preview.get("description", ""),
                    "name": simple_preview.get("name", ""),
                }

                # Extract type-specific details
                if action_type == "TonTransfer":
                    detail = action.get("TonTransfer", {})
                    entry["amount_ton"] = float(detail.get("amount", 0)) / 1e9
                    entry["sender"] = detail.get("sender", {}).get("address")
                    entry["recipient"] = detail.get("recipient", {}).get("address")
                elif action_type == "JettonTransfer":
                    detail = action.get("JettonTransfer", {})
                    jetton = detail.get("jetton", {})
                    decimals = jetton.get("decimals", 9)
                    entry["amount"] = float(detail.get("amount", 0)) / (10 ** decimals)
                    entry["symbol"] = jetton.get("symbol")
                    entry["jetton_address"] = jetton.get("address")
                    entry["sender"] = detail.get("sender", {}).get("address")
                    entry["recipient"] = detail.get("recipient", {}).get("address")
                elif action_type == "JettonSwap":
                    detail = action.get("JettonSwap", {})
                    entry["dex"] = detail.get("dex", "Unknown")
                    entry["amount_in"] = detail.get("amount_in")
                    entry["amount_out"] = detail.get("amount_out")
                    jin = detail.get("jetton_master_in", {})
                    jout = detail.get("jetton_master_out", {})
                    entry["token_in"] = jin.get("symbol") if jin else "TON"
                    entry["token_out"] = jout.get("symbol") if jout else "TON"
                elif action_type == "NftItemTransfer":
                    detail = action.get("NftItemTransfer", {})
                    entry["nft_address"] = detail.get("nft", "")
                    entry["sender"] = detail.get("sender", {}).get("address")
                    entry["recipient"] = detail.get("recipient", {}).get("address")

                actions_summary.append(entry)

            return {
                "event_id": event.get("event_id"),
                "timestamp": event.get("timestamp"),
                "is_scam": event.get("is_scam", False),
                "in_progress": event.get("in_progress", False),
                "actions": actions_summary,
                "lt": event.get("lt"),
            }
        except Exception as e:
            # Fallback to raw blockchain transaction
            try:
                raw_tx = await self.ton_client.get_transaction(tx_hash)
                return {
                    "raw_transaction": raw_tx,
                    "note": "Event view unavailable, showing raw blockchain transaction.",
                }
            except Exception as e2:
                return {"error": f"Could not fetch transaction: {e2}"}

    # =================================================================
    # 3. find_hot_trends
    # =================================================================

    async def find_hot_trends(self, category: str = "tokens") -> Dict[str, Any]:
        """Find trending tokens, pools, or new pools on TON.
        Data sourced from GeckoTerminal (real trending algorithm based on volume and activity).
        """
        try:
            if category == "tokens":
                return await self._get_trending_tokens()
            elif category == "pools":
                return await self._get_trending_pools()
            elif category == "new_pools":
                return await self._get_new_pools()
            else:
                return {"error": f"Unknown category '{category}'. Use: tokens, pools, new_pools"}
        except Exception as e:
            logger.error(f"Error in find_hot_trends: {e}")
            return {"error": str(e)}

    async def _get_trending_tokens(self) -> Dict[str, Any]:
        """Extract unique trending tokens from GeckoTerminal trending pools."""
        raw = await self.gecko_client.get_trending_pools(include_tokens=True)
        pools = raw.get("data", [])
        included = raw.get("included", [])

        # Build token lookup from included array
        token_lookup = {}
        for item in included:
            if item.get("type") == "token":
                token_lookup[item["id"]] = item.get("attributes", {})

        # Aggregate token data across pools
        token_agg: Dict[str, Dict] = {}

        for pool in pools:
            attrs = pool.get("attributes", {})
            vol_24h = float(attrs.get("volume_usd", {}).get("h24") or 0)
            txs_24h = attrs.get("transactions", {}).get("h24", {})
            price_change_h24 = attrs.get("price_change_percentage", {}).get("h24")
            fdv = attrs.get("fdv_usd")
            reserve = attrs.get("reserve_in_usd")
            pool_name = attrs.get("name", "")

            rels = pool.get("relationships", {})
            for role in ["base_token", "quote_token"]:
                token_ref = rels.get(role, {}).get("data", {})
                token_id = token_ref.get("id")
                if not token_id or token_id not in token_lookup:
                    continue

                token_attrs = token_lookup[token_id]
                symbol = token_attrs.get("symbol", "")
                if symbol.upper() in _SKIP_SYMBOLS:
                    continue

                address = token_attrs.get("address", token_id.replace("ton_", "", 1))

                if address not in token_agg:
                    # Get price from pool attributes
                    price_usd = None
                    if role == "base_token":
                        price_usd = attrs.get("base_token_price_usd")
                    elif role == "quote_token":
                        price_usd = attrs.get("quote_token_price_usd")

                    token_agg[address] = {
                        "address": address,
                        "name": token_attrs.get("name", "Unknown"),
                        "symbol": symbol,
                        "image_url": token_attrs.get("image_url"),
                        "price_usd": float(price_usd) if price_usd else None,
                        "total_volume_24h": 0,
                        "total_buys_24h": 0,
                        "total_sells_24h": 0,
                        "price_change_24h": None,
                        "fdv_usd": None,
                        "total_liquidity_usd": 0,
                        "pool_count": 0,
                        "pools": [],
                    }

                entry = token_agg[address]
                entry["total_volume_24h"] += vol_24h
                entry["total_buys_24h"] += int(txs_24h.get("buys", 0))
                entry["total_sells_24h"] += int(txs_24h.get("sells", 0))
                entry["total_liquidity_usd"] += float(reserve) if reserve else 0
                entry["pool_count"] += 1
                entry["pools"].append(pool_name)

                if price_change_h24 is not None:
                    pc = float(price_change_h24)
                    if entry["price_change_24h"] is None or abs(pc) > abs(entry["price_change_24h"]):
                        entry["price_change_24h"] = pc

                if fdv is not None:
                    fdv_f = float(fdv)
                    if entry["fdv_usd"] is None or fdv_f > entry["fdv_usd"]:
                        entry["fdv_usd"] = fdv_f

        # Sort by 24h volume descending
        tokens_sorted = sorted(token_agg.values(), key=lambda t: t["total_volume_24h"], reverse=True)

        return {
            "trending_tokens": tokens_sorted,
            "total_unique_tokens": len(tokens_sorted),
            "source": "geckoterminal",
        }

    async def _get_trending_pools(self) -> Dict[str, Any]:
        """Get trending pools from GeckoTerminal."""
        raw = await self.gecko_client.get_trending_pools(include_tokens=True)
        pools = raw.get("data", [])
        included = raw.get("included", [])

        token_lookup = {}
        for item in included:
            if item.get("type") == "token":
                token_lookup[item["id"]] = item.get("attributes", {})

        result_pools = []
        for pool in pools:
            attrs = pool.get("attributes", {})
            rels = pool.get("relationships", {})

            base_id = rels.get("base_token", {}).get("data", {}).get("id", "")
            quote_id = rels.get("quote_token", {}).get("data", {}).get("id", "")
            base_attrs = token_lookup.get(base_id, {})
            quote_attrs = token_lookup.get(quote_id, {})
            dex_id = rels.get("dex", {}).get("data", {}).get("id", "")

            result_pools.append({
                "name": attrs.get("name"),
                "address": attrs.get("address"),
                "dex": dex_id,
                "base_token": {"symbol": base_attrs.get("symbol"), "address": base_attrs.get("address")},
                "quote_token": {"symbol": quote_attrs.get("symbol"), "address": quote_attrs.get("address")},
                "volume_usd_24h": attrs.get("volume_usd", {}).get("h24"),
                "transactions_24h": attrs.get("transactions", {}).get("h24"),
                "price_change_24h": attrs.get("price_change_percentage", {}).get("h24"),
                "fdv_usd": attrs.get("fdv_usd"),
                "liquidity_usd": attrs.get("reserve_in_usd"),
                "created_at": attrs.get("pool_created_at"),
            })

        return {"trending_pools": result_pools, "source": "geckoterminal"}

    async def _get_new_pools(self) -> Dict[str, Any]:
        """Get newly created pools from GeckoTerminal."""
        raw = await self.gecko_client.get_new_pools(include_tokens=True)
        pools = raw.get("data", [])
        included = raw.get("included", [])

        token_lookup = {}
        for item in included:
            if item.get("type") == "token":
                token_lookup[item["id"]] = item.get("attributes", {})

        result_pools = []
        for pool in pools:
            attrs = pool.get("attributes", {})
            rels = pool.get("relationships", {})

            base_id = rels.get("base_token", {}).get("data", {}).get("id", "")
            quote_id = rels.get("quote_token", {}).get("data", {}).get("id", "")
            base_attrs = token_lookup.get(base_id, {})
            quote_attrs = token_lookup.get(quote_id, {})

            result_pools.append({
                "name": attrs.get("name"),
                "address": attrs.get("address"),
                "base_token": {"symbol": base_attrs.get("symbol"), "address": base_attrs.get("address")},
                "quote_token": {"symbol": quote_attrs.get("symbol"), "address": quote_attrs.get("address")},
                "volume_usd_24h": attrs.get("volume_usd", {}).get("h24"),
                "liquidity_usd": attrs.get("reserve_in_usd"),
                "created_at": attrs.get("pool_created_at"),
            })

        return {"new_pools": result_pools, "source": "geckoterminal"}

    # =================================================================
    # 4. analyze_trading_patterns (binary: full report or error)
    # =================================================================

    async def analyze_trading_patterns(self, address: str, timeframe: str = "24h") -> Dict[str, Any]:
        """Analyze trading patterns. Returns full analysis or error if too many events."""
        try:
            assert_full_address(address)

            now = datetime.utcnow()
            end_date = int(now.timestamp())
            start_date = self._parse_timeframe(now, timeframe)

            events = await self._fetch_all_events(address, start_date, end_date)

            if not events:
                return {
                    "address": address,
                    "timeframe": timeframe,
                    "total_events": 0,
                    "message": "No events found for this address in the specified timeframe.",
                }

            # Analyze events
            jetton_transfers = 0
            dex_swaps = 0
            ton_transfers = 0
            other_actions = 0
            trading_volume_raw = 0
            unique_tokens = set()
            dex_list = []

            for event in events:
                for action in event.get("actions", []):
                    action_type = action.get("type", "")

                    if action_type == "JettonTransfer":
                        jetton_transfers += 1
                        detail = action.get("JettonTransfer", {})
                        amount = detail.get("amount")
                        jetton = detail.get("jetton", {})
                        if jetton.get("symbol"):
                            unique_tokens.add(jetton["symbol"])
                        if amount:
                            try:
                                trading_volume_raw += int(amount)
                            except (ValueError, TypeError):
                                pass

                    elif action_type == "JettonSwap":
                        dex_swaps += 1
                        detail = action.get("JettonSwap", {})
                        dex_name = detail.get("dex", "Unknown")
                        if dex_name not in dex_list:
                            dex_list.append(dex_name)
                        jin = detail.get("jetton_master_in", {})
                        jout = detail.get("jetton_master_out", {})
                        if jin and jin.get("symbol"):
                            unique_tokens.add(jin["symbol"])
                        if jout and jout.get("symbol"):
                            unique_tokens.add(jout["symbol"])
                        amount_in = detail.get("amount_in")
                        if amount_in:
                            try:
                                trading_volume_raw += int(amount_in)
                            except (ValueError, TypeError):
                                pass

                    elif action_type == "TonTransfer":
                        ton_transfers += 1
                    else:
                        other_actions += 1

            total_events = len(events)
            total_actions = jetton_transfers + dex_swaps + ton_transfers + other_actions
            is_active_trader = dex_swaps > 10
            trading_frequency = (dex_swaps / max(1, total_actions)) * 100

            return {
                "address": address,
                "timeframe": timeframe,
                "total_events": total_events,
                "jetton_transfers": jetton_transfers,
                "dex_swaps": dex_swaps,
                "ton_transfers": ton_transfers,
                "other_actions": other_actions,
                "unique_tokens_traded": sorted(unique_tokens),
                "dexes_used": dex_list,
                "is_active_trader": is_active_trader,
                "trading_frequency_pct": round(trading_frequency, 1),
            }

        except TooManyEventsError as e:
            return {"error": str(e)}
        except ValueError as e:
            return {"error": f"Invalid address: {e}"}
        except Exception as e:
            logger.error(f"Error in analyze_trading_patterns: {e}", exc_info=True)
            return {"error": str(e)}

    async def _fetch_all_events(self, address: str, start_date: int, end_date: int) -> List[Dict]:
        """Fetch ALL events in a time range with pagination.
        Raises TooManyEventsError if event count exceeds max_events.
        """
        all_events = []
        before_lt = None

        while True:
            kwargs = {
                "address": address,
                "start_date": start_date,
                "end_date": end_date,
                "limit": _PAGE_SIZE,
            }
            if before_lt is not None:
                kwargs["before_lt"] = before_lt

            response = await self.ton_client.get_account_transactions(**kwargs)
            events = response.get("events", [])

            if not events:
                break

            all_events.extend(events)

            if len(all_events) > self.max_events:
                raise TooManyEventsError(
                    f"More than {self.max_events} events found in this timeframe "
                    f"(fetched {len(all_events)} so far). "
                    f"Please use a shorter timeframe for analysis."
                )

            next_from = response.get("next_from")
            if not next_from:
                break

            before_lt = int(next_from)

        return all_events

    def _parse_timeframe(self, now: datetime, timeframe: str) -> int:
        """Parse timeframe string to unix timestamp (start_date)."""
        tf = timeframe.strip().lower()
        if tf.endswith("y"):
            years = int(tf[:-1])
            return int((now - timedelta(days=365 * years)).timestamp())
        elif tf.endswith("d"):
            days = int(tf[:-1])
            return int((now - timedelta(days=days)).timestamp())
        elif tf.endswith("h"):
            hours = int(tf[:-1])
            return int((now - timedelta(hours=hours)).timestamp())
        else:
            # Default 24h
            return int((now - timedelta(hours=24)).timestamp())

    # =================================================================
    # 5. get_ton_price
    # =================================================================

    async def get_ton_price(self, currency: str = "usd") -> Dict[str, Any]:
        """Get real-time TON price."""
        try:
            return await self.ton_client.get_ton_price(currency=currency)
        except Exception as e:
            return {"error": str(e)}

    # =================================================================
    # 6. get_jetton_price
    # =================================================================

    async def get_jetton_price(self, tokens: List[str], currency: str = "usd") -> Dict[str, Any]:
        """Get jetton token prices."""
        try:
            return await self.ton_client.get_jetton_price(tokens=tokens, currency=currency)
        except Exception as e:
            return {"error": str(e)}

    # =================================================================
    # 7. get_jetton_info
    # =================================================================

    async def get_jetton_info(self, jetton_address: str) -> Dict[str, Any]:
        """Get detailed jetton metadata + current price."""
        try:
            assert_full_address(jetton_address)
            info = await self.ton_client.get_jetton_info(jetton_address)

            # Enrich with price
            price_data = await self.ton_client.get_jetton_price(
                tokens=[jetton_address], currency="usd"
            )
            token_price = price_data.get(jetton_address, {})

            metadata = info.get("metadata", {})
            return {
                "address": jetton_address,
                "name": metadata.get("name"),
                "symbol": metadata.get("symbol"),
                "decimals": metadata.get("decimals"),
                "description": metadata.get("description"),
                "image": metadata.get("image"),
                "total_supply": info.get("total_supply"),
                "mintable": info.get("mintable"),
                "holders_count": info.get("holders_count"),
                "verification": info.get("verification"),
                "price_usd": token_price.get("price"),
                "diff_24h": token_price.get("diff_24h"),
                "diff_7d": token_price.get("diff_7d"),
                "diff_30d": token_price.get("diff_30d"),
                "social": metadata.get("social", []),
                "websites": metadata.get("websites", []),
            }
        except ValueError as e:
            return {"error": f"Invalid address: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # =================================================================
    # 8. get_jetton_holders
    # =================================================================

    async def get_jetton_holders(self, jetton_address: str, limit: int = 100) -> Dict[str, Any]:
        """Get top holders of a jetton with human-readable balances."""
        try:
            assert_full_address(jetton_address)

            # Get jetton info for decimals
            info = await self.ton_client.get_jetton_info(jetton_address)
            decimals = int(info.get("metadata", {}).get("decimals", 9))
            symbol = info.get("metadata", {}).get("symbol", "TOKEN")
            total_supply = info.get("total_supply", "0")

            holders_data = await self.ton_client.get_jetton_holders(
                jetton_address, limit=min(limit, 1000)
            )

            holders = []
            for h in holders_data.get("addresses", []):
                raw_balance = int(h.get("balance", 0))
                human_balance = raw_balance / (10 ** decimals)
                owner = h.get("owner", {})
                holders.append({
                    "owner_address": owner.get("address"),
                    "owner_name": owner.get("name"),
                    "balance": human_balance,
                    "balance_raw": str(raw_balance),
                })

            return {
                "jetton_address": jetton_address,
                "symbol": symbol,
                "decimals": decimals,
                "total_holders": holders_data.get("total", 0),
                "showing": len(holders),
                "holders": holders,
            }
        except ValueError as e:
            return {"error": f"Invalid address: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # =================================================================
    # 9. resolve_ton_domain
    # =================================================================

    async def resolve_ton_domain(self, domain: str) -> Dict[str, Any]:
        """Resolve a .ton domain name to address and records."""
        try:
            result = await self.ton_client.resolve_dns(domain)
            return {
                "domain": domain,
                "resolved": result,
            }
        except Exception as e:
            return {"error": f"Could not resolve domain '{domain}': {e}"}

    # =================================================================
    # 10. get_wallet_jettons
    # =================================================================

    async def get_wallet_jettons(self, address: str) -> Dict[str, Any]:
        """Get all jetton balances for a wallet with USD prices."""
        try:
            assert_full_address(address)
            balances = await self.ton_client.get_jetton_balances(address, currencies=["usd"])

            jettons = []
            total_usd = 0
            for b in balances.get("balances", []):
                j_meta = b.get("jetton", {})
                decimals = j_meta.get("decimals", 9)
                balance = float(b.get("balance", 0)) / (10 ** decimals)
                price_info = b.get("price", {})
                price = float(price_info.get("prices", {}).get("USD", 0) or 0) if price_info else 0
                usd_value = balance * price
                total_usd += usd_value

                jettons.append({
                    "symbol": j_meta.get("symbol", "Unknown"),
                    "name": j_meta.get("name", "Unknown"),
                    "address": j_meta.get("address"),
                    "balance": balance,
                    "price_usd": price,
                    "usd_value": usd_value,
                    "verification": j_meta.get("verification"),
                })

            # Sort by USD value descending
            jettons.sort(key=lambda x: x["usd_value"], reverse=True)

            return {
                "address": address,
                "total_jettons": len(jettons),
                "total_usd_value": total_usd,
                "jettons": jettons,
            }
        except ValueError as e:
            return {"error": f"Invalid address: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # =================================================================
    # 11. get_blockchain_status
    # =================================================================

    async def get_blockchain_status(self) -> Dict[str, Any]:
        """Get TON blockchain status: latest block, validators, and time."""
        try:
            head = await self.ton_client.get_blockchain_masterchain_head()
            validators = await self.ton_client.get_blockchain_validators()

            validator_list = validators.get("validators", [])

            return {
                "masterchain_seqno": head.get("seqno"),
                "masterchain_time": head.get("gen_utime"),
                "tx_in_last_block": head.get("tx_quantity"),
                "validator_count": len(validator_list),
                "global_id": head.get("global_id"),
            }
        except Exception as e:
            return {"error": str(e)}

    # =================================================================
    # 12. get_token_market_data
    # =================================================================

    async def get_token_market_data(self, token_address: str) -> Dict[str, Any]:
        """Get market data for a TON token from GeckoTerminal."""
        try:
            result = await self.gecko_client.get_token_info(token_address)
            data = result.get("data", {})
            attrs = data.get("attributes", {})

            top_pools_refs = data.get("relationships", {}).get("top_pools", {}).get("data", [])
            top_pool_addresses = [p.get("id", "").replace("ton_", "", 1) for p in top_pools_refs]

            return {
                "address": attrs.get("address", token_address),
                "name": attrs.get("name"),
                "symbol": attrs.get("symbol"),
                "decimals": attrs.get("decimals"),
                "price_usd": attrs.get("price_usd"),
                "fdv_usd": attrs.get("fdv_usd"),
                "market_cap_usd": attrs.get("market_cap_usd"),
                "volume_usd_24h": attrs.get("volume_usd", {}).get("h24"),
                "total_reserve_usd": attrs.get("total_reserve_in_usd"),
                "image_url": attrs.get("image_url"),
                "coingecko_coin_id": attrs.get("coingecko_coin_id"),
                "top_pool_addresses": top_pool_addresses,
                "source": "geckoterminal",
            }
        except Exception as e:
            return {"error": f"Could not fetch market data for {token_address}: {e}"}

    # =================================================================
    # 13. get_account_events
    # =================================================================

    async def get_account_events(self, address: str, limit: int = 25, before_lt: int = None) -> Dict[str, Any]:
        """Get recent events for an address with pagination support.
        Agent passes next_before_lt from response as before_lt to get next page.
        """
        try:
            assert_full_address(address)

            effective_limit = max(1, min(limit, 100))
            kwargs = {"address": address, "limit": effective_limit}
            if before_lt is not None:
                kwargs["before_lt"] = before_lt

            resp = await self.ton_client.get_account_transactions(**kwargs)
            events = resp.get("events", [])
            next_from = resp.get("next_from")

            # Format events into summary
            formatted_events = []
            for event in events:
                actions_brief = []
                for action in event.get("actions", []):
                    action_type = action.get("type", "Unknown")
                    preview = action.get("simple_preview", {})
                    actions_brief.append({
                        "type": action_type,
                        "description": preview.get("description", ""),
                    })

                formatted_events.append({
                    "event_id": event.get("event_id"),
                    "timestamp": event.get("timestamp"),
                    "is_scam": event.get("is_scam", False),
                    "actions": actions_brief,
                    "lt": event.get("lt"),
                })

            return {
                "address": address,
                "events": formatted_events,
                "count": len(formatted_events),
                "has_more": next_from is not None,
                "next_before_lt": int(next_from) if next_from else None,
            }
        except ValueError as e:
            return {"error": f"Invalid address: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # =================================================================
    # 14. get_staking_info
    # =================================================================

    async def get_staking_info(self, address: str = None) -> Dict[str, Any]:
        """Dual mode: list staking pools (no address) or show staking positions (with address)."""
        try:
            if address:
                assert_full_address(address)
                positions = await self.ton_client.get_nominator_pools(address)
                pools_data = positions.get("pools", [])

                formatted = []
                for pool in pools_data:
                    formatted.append({
                        "pool_address": pool.get("address"),
                        "pool_name": pool.get("name"),
                        "amount_staked": float(pool.get("amount", 0)) / 1e9,
                        "pending_deposit": float(pool.get("pending_deposit", 0)) / 1e9,
                        "pending_withdraw": float(pool.get("pending_withdraw", 0)) / 1e9,
                        "ready_withdraw": float(pool.get("ready_withdraw", 0)) / 1e9,
                    })

                return {
                    "address": address,
                    "staking_positions": formatted,
                    "total_positions": len(formatted),
                }
            else:
                # List available staking pools
                result = await self.ton_client.get_staking_pools()
                pools = result.get("pools", [])

                formatted = []
                for pool in pools:
                    formatted.append({
                        "address": pool.get("address"),
                        "name": pool.get("name"),
                        "apy": pool.get("apy"),
                        "min_stake": float(pool.get("min_stake", 0)) / 1e9,
                        "current_nominators": pool.get("current_nominators"),
                        "max_nominators": pool.get("max_nominators"),
                        "total_amount": float(pool.get("total_amount", 0)) / 1e9,
                        "verified": pool.get("verified", False),
                        "cycle_end": pool.get("cycle_end"),
                    })

                # Sort by APY descending
                formatted.sort(key=lambda x: float(x.get("apy") or 0), reverse=True)

                return {
                    "available_pools": formatted,
                    "total_pools": len(formatted),
                    "implementations": result.get("implementations", {}),
                }
        except ValueError as e:
            return {"error": f"Invalid address: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # =================================================================
    # 15. get_nft_info
    # =================================================================

    async def get_nft_info(self, nft_address: str) -> Dict[str, Any]:
        """Get NFT item or collection info by address."""
        try:
            assert_full_address(nft_address)

            # Try as NFT item first
            try:
                item = await self.ton_client.get_nft_item(nft_address)
                collection = item.get("collection", {})
                metadata = item.get("metadata", {})
                owner = item.get("owner", {})

                return {
                    "type": "nft_item",
                    "address": nft_address,
                    "name": metadata.get("name"),
                    "description": metadata.get("description"),
                    "image": metadata.get("image"),
                    "owner_address": owner.get("address"),
                    "owner_name": owner.get("name"),
                    "collection_address": collection.get("address"),
                    "collection_name": collection.get("name"),
                    "verified": item.get("approved_by") is not None,
                    "index": item.get("index"),
                }
            except Exception:
                pass

            # Try as NFT collection
            try:
                collection = await self.ton_client.get_nft_collection(nft_address)
                metadata = collection.get("metadata", {})
                return {
                    "type": "nft_collection",
                    "address": nft_address,
                    "name": metadata.get("name"),
                    "description": metadata.get("description"),
                    "image": metadata.get("image"),
                    "next_item_index": collection.get("next_item_index"),
                    "owner_address": collection.get("owner", {}).get("address"),
                }
            except Exception:
                pass

            return {"error": f"Address {nft_address} is neither an NFT item nor a collection."}

        except ValueError as e:
            return {"error": f"Invalid address: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # =================================================================
    # Internal helpers
    # =================================================================

    def _analyze_events(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze a list of events for basic patterns."""
        if not events:
            return {}

        action_types = {}
        for event in events:
            for action in event.get("actions", []):
                atype = action.get("type", "Unknown")
                action_types[atype] = action_types.get(atype, 0) + 1

        timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
        first_ts = min(timestamps) if timestamps else None
        last_ts = max(timestamps) if timestamps else None

        return {
            "events_analyzed": len(events),
            "action_type_breakdown": action_types,
            "earliest_event": first_ts,
            "latest_event": last_ts,
        }
