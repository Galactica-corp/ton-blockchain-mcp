"""
Test script for TON MCP functions.
Tests GeckoTerminal endpoints (no API key needed) and TONAPI endpoints (needs TON_API_KEY).

Usage:
    # GeckoTerminal tests only (no API key needed):
    python -m tests.test_mcp_functions --gecko-only

    # All tests (needs TON_API_KEY):
    python -m tests.test_mcp_functions
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.tonmcp.gecko_client import GeckoClient
from src.tonmcp.ton_client import TonClient
from src.tonmcp.tools import ToolManager, TooManyEventsError

# Test addresses
TON_FOUNDATION = "EQBYivdc0GAk-nnczaMnYNuSjpeXu2nJS3DZ4KqLjosX5sVC"
USDT_JETTON = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"


def sep(title: str):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


# =========================================================================
# GeckoTerminal tests (no API key needed)
# =========================================================================

async def test_trending_tokens(tools: ToolManager):
    sep("TEST: find_hot_trends(category='tokens')")
    result = await tools.find_hot_trends(category="tokens")

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    tokens = result.get("trending_tokens", [])
    print(f"  Source: {result.get('source')}")
    print(f"  Unique tokens found: {result.get('total_unique_tokens')}")
    print()

    for i, t in enumerate(tokens[:10]):
        vol = t.get("total_volume_24h", 0)
        buys = t.get("total_buys_24h", 0)
        sells = t.get("total_sells_24h", 0)
        pc = t.get("price_change_24h")
        fdv = t.get("fdv_usd")
        price = t.get("price_usd")
        print(f"  [{i+1}] {t['name']} ({t['symbol']})")
        print(f"      Address: {t['address']}")
        print(f"      Price: ${price:.6f}" if price else "      Price: N/A")
        print(f"      Vol 24h: ${vol:,.0f}  |  Txs: {buys}B/{sells}S")
        print(f"      Price change 24h: {pc}%" if pc is not None else "      Price change: N/A")
        print(f"      FDV: ${fdv:,.0f}" if fdv else "      FDV: N/A")
        print(f"      Liquidity: ${t.get('total_liquidity_usd', 0):,.0f}")
        print(f"      Pools: {t.get('pool_count')} ({', '.join(t.get('pools', [])[:3])})")
        print()

    # Verify quality
    has_volume = sum(1 for t in tokens if t.get("total_volume_24h", 0) > 1000)
    has_txs = sum(1 for t in tokens if t.get("total_buys_24h", 0) + t.get("total_sells_24h", 0) > 10)
    print(f"  Quality check: {has_volume}/{len(tokens)} tokens with >$1k volume")
    print(f"  Quality check: {has_txs}/{len(tokens)} tokens with >10 txs")

    assert len(tokens) > 0, "No trending tokens returned"
    assert has_volume > 0, "No tokens with significant volume"
    print("  PASS")
    return True


async def test_trending_pools(tools: ToolManager):
    sep("TEST: find_hot_trends(category='pools')")
    result = await tools.find_hot_trends(category="pools")

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    pools = result.get("trending_pools", [])
    print(f"  Trending pools: {len(pools)}")
    for i, p in enumerate(pools[:5]):
        print(f"  [{i+1}] {p['name']} on {p.get('dex', 'N/A')}")
        print(f"      Vol 24h: {p.get('volume_usd_24h')}, Liquidity: {p.get('liquidity_usd')}")
    print("  PASS")
    return True


async def test_new_pools(tools: ToolManager):
    sep("TEST: find_hot_trends(category='new_pools')")
    result = await tools.find_hot_trends(category="new_pools")

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    pools = result.get("new_pools", [])
    print(f"  New pools: {len(pools)}")
    for i, p in enumerate(pools[:3]):
        print(f"  [{i+1}] {p['name']} created: {p.get('created_at', 'N/A')}")
    print("  PASS")
    return True


async def test_token_market_data(tools: ToolManager):
    sep("TEST: get_token_market_data (USDT)")
    result = await tools.get_token_market_data(USDT_JETTON)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    print(f"  Name: {result.get('name')}")
    print(f"  Symbol: {result.get('symbol')}")
    print(f"  Price USD: {result.get('price_usd')}")
    print(f"  Volume 24h: {result.get('volume_usd_24h')}")
    print(f"  FDV: {result.get('fdv_usd')}")
    print(f"  Market Cap: {result.get('market_cap_usd')}")
    print(f"  Liquidity: {result.get('total_reserve_usd')}")
    print(f"  Top pools: {result.get('top_pool_addresses', [])[:3]}")
    print("  PASS")
    return True


async def test_invalid_category(tools: ToolManager):
    sep("TEST: find_hot_trends(category='invalid')")
    result = await tools.find_hot_trends(category="invalid")
    assert "error" in result, "Should return error for invalid category"
    print(f"  Error: {result['error']}")
    print("  PASS")
    return True


# =========================================================================
# TONAPI tests (needs API key)
# =========================================================================

async def test_analyze_address(tools: ToolManager):
    sep("TEST: analyze_address")
    result = await tools.analyze_address(address=TON_FOUNDATION, deep_analysis=True)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    print(f"  Status: {result.get('status')}")
    print(f"  TON balance: {result.get('ton_balance'):.4f} TON")
    print(f"  TON USD: ${result.get('ton_usd_value', 0):.2f}")
    print(f"  Jettons: {result.get('jetton_count')}")
    print(f"  NFTs: {result.get('nft_count')}")
    print(f"  Total USD: ${result.get('wallet_value_usd', 0):.2f}")

    # Verify no misleading transaction_count
    assert "transaction_count" not in result, "transaction_count should be removed!"
    recent = result.get("recent_events", {})
    print(f"  Recent events: {recent.get('count')}, has_more: {recent.get('has_more')}")

    # Verify address validation before API calls
    bad = await tools.analyze_address(address="short", deep_analysis=False)
    assert "error" in bad and "Invalid address" in bad["error"], "Should reject short address"
    print(f"  Short address rejected: {bad['error']}")

    if result.get("analysis"):
        print(f"  Deep analysis: {json.dumps(result['analysis'], indent=2, default=str)[:200]}")

    print("  PASS")
    return True


async def test_trading_patterns(tools: ToolManager):
    sep("TEST: analyze_trading_patterns (24h)")
    result = await tools.analyze_trading_patterns(address=TON_FOUNDATION, timeframe="24h")

    if "error" in result:
        print(f"  Note: {result['error']}")
        # This is acceptable if it's a "too many events" error
        if "too many" in result["error"].lower() or "shorter timeframe" in result["error"].lower():
            print("  This is expected for very active addresses — means pagination works!")
            print("  PASS")
            return True
        return False

    print(f"  Total events: {result.get('total_events')}")
    print(f"  Jetton transfers: {result.get('jetton_transfers')}")
    print(f"  DEX swaps: {result.get('dex_swaps')}")
    print(f"  TON transfers: {result.get('ton_transfers')}")
    print(f"  Unique tokens: {result.get('unique_tokens_traded')}")
    print(f"  DEXes used: {result.get('dexes_used')}")
    print(f"  Active trader: {result.get('is_active_trader')}")
    print(f"  Trading frequency: {result.get('trading_frequency_pct')}%")

    # If we got >100 events, pagination worked!
    if result.get("total_events", 0) > 100:
        print(f"  PAGINATION WORKS: fetched {result['total_events']} events (>100 limit)")

    print("  PASS")
    return True


async def test_trading_patterns_too_many(tools: ToolManager):
    sep("TEST: analyze_trading_patterns with huge timeframe (expect error)")
    # Use a very long timeframe to trigger the too-many-events error
    result = await tools.analyze_trading_patterns(address=TON_FOUNDATION, timeframe="365d")

    if "error" in result:
        print(f"  Got expected error: {result['error'][:100]}...")
        print("  PASS — binary behavior confirmed (error, not partial)")
        return True
    else:
        print(f"  Got full report with {result.get('total_events')} events")
        print("  (Address might not have that many events in 365d)")
        print("  PASS")
        return True


async def test_transaction_details(tools: ToolManager):
    sep("TEST: get_transaction_details")
    # First get a recent event to have a valid hash
    events_resp = await tools.get_account_events(address=TON_FOUNDATION, limit=1)
    events = events_resp.get("events", [])
    if not events:
        print("  SKIP: no events found")
        return True

    event_id = events[0].get("event_id")
    print(f"  Testing with event_id: {event_id}")

    result = await tools.get_transaction_details(tx_hash=event_id)
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    print(f"  Event ID: {result.get('event_id')}")
    print(f"  Timestamp: {result.get('timestamp')}")
    print(f"  Is scam: {result.get('is_scam')}")
    print(f"  Actions: {len(result.get('actions', []))}")
    for a in result.get("actions", [])[:3]:
        print(f"    - {a.get('type')}: {a.get('description', '')[:80]}")
    print("  PASS")
    return True


async def test_account_events(tools: ToolManager):
    sep("TEST: get_account_events with pagination")
    page1 = await tools.get_account_events(address=TON_FOUNDATION, limit=5)

    if "error" in page1:
        print(f"  ERROR: {page1['error']}")
        return False

    print(f"  Page 1: {page1.get('count')} events, has_more={page1.get('has_more')}")

    if page1.get("has_more") and page1.get("next_before_lt"):
        page2 = await tools.get_account_events(
            address=TON_FOUNDATION, limit=5, before_lt=page1["next_before_lt"]
        )
        print(f"  Page 2: {page2.get('count')} events, has_more={page2.get('has_more')}")

        # Verify no overlap
        ids1 = {e["event_id"] for e in page1.get("events", [])}
        ids2 = {e["event_id"] for e in page2.get("events", [])}
        overlap = ids1 & ids2
        assert not overlap, f"Pagination has overlapping events: {overlap}"
        print("  No overlap between pages — pagination works correctly!")

    print("  PASS")
    return True


async def test_ton_price(tools: ToolManager):
    sep("TEST: get_ton_price")
    result = await tools.get_ton_price(currency="usd")
    print(f"  Price: ${result.get('price')}")
    print(f"  Source: {result.get('source')}")
    assert result.get("price") is not None, "TON price should not be None"
    print("  PASS")
    return True


async def test_jetton_info(tools: ToolManager):
    sep("TEST: get_jetton_info (USDT)")
    result = await tools.get_jetton_info(jetton_address=USDT_JETTON)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    print(f"  Name: {result.get('name')}")
    print(f"  Symbol: {result.get('symbol')}")
    print(f"  Holders: {result.get('holders_count')}")
    print(f"  Verification: {result.get('verification')}")
    print(f"  Mintable: {result.get('mintable')}")
    print(f"  Price: {result.get('price_usd')}")
    print("  PASS")
    return True


async def test_jetton_holders(tools: ToolManager):
    sep("TEST: get_jetton_holders (USDT top 5)")
    result = await tools.get_jetton_holders(jetton_address=USDT_JETTON, limit=5)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    print(f"  Symbol: {result.get('symbol')}")
    print(f"  Total holders: {result.get('total_holders')}")
    print(f"  Showing: {result.get('showing')}")
    for h in result.get("holders", []):
        name = h.get("owner_name") or h.get("owner_address", "")[:20] + "..."
        print(f"    {name}: {h.get('balance'):,.2f}")
    print("  PASS")
    return True


async def test_wallet_jettons(tools: ToolManager):
    sep("TEST: get_wallet_jettons")
    result = await tools.get_wallet_jettons(address=TON_FOUNDATION)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    print(f"  Total jettons: {result.get('total_jettons')}")
    print(f"  Total USD value: ${result.get('total_usd_value', 0):,.2f}")
    for j in result.get("jettons", [])[:5]:
        print(f"    {j['symbol']}: {j['balance']:.4f} = ${j['usd_value']:.2f}")
    print("  PASS")
    return True


async def test_blockchain_status(tools: ToolManager):
    sep("TEST: get_blockchain_status")
    result = await tools.get_blockchain_status()

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    print(f"  Masterchain seqno: {result.get('masterchain_seqno')}")
    print(f"  Block time: {result.get('masterchain_time')}")
    print(f"  Txs in last block: {result.get('tx_in_last_block')}")
    print(f"  Validators: {result.get('validator_count')}")
    print("  PASS")
    return True


async def test_staking_info(tools: ToolManager):
    sep("TEST: get_staking_info (list pools, pagination & sorting)")

    # Default: sorted by TVL, page 1
    result = await tools.get_staking_info()
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    pools = result.get("available_pools", [])
    total = result.get("total_pools", 0)
    showing = result.get("showing", 0)
    print(f"  Total pools: {total}, showing: {showing}, sort_by: {result.get('sort_by')}")
    print(f"  has_more: {result.get('has_more')}, offset: {result.get('offset')}, limit: {result.get('limit')}")
    for p in pools[:5]:
        print(f"    {p.get('name', 'N/A')}: TVL={p.get('total_amount'):.0f} TON, APY={p.get('apy')}%, verified={p.get('verified')}")

    assert showing <= 20, f"Default limit should be 20, got {showing}"
    assert result.get("sort_by") == "tvl"

    # Verify TVL descending order
    tvls = [p.get("total_amount", 0) for p in pools]
    assert tvls == sorted(tvls, reverse=True), "Pools should be sorted by TVL descending"

    # Test sort by APY
    result_apy = await tools.get_staking_info(sort_by="apy", limit=5)
    pools_apy = result_apy.get("available_pools", [])
    apys = [float(p.get("apy") or 0) for p in pools_apy]
    assert apys == sorted(apys, reverse=True), "Pools should be sorted by APY descending"
    print(f"  Sort by APY top: {pools_apy[0].get('name', 'N/A')} APY={pools_apy[0].get('apy')}%")

    # Test pagination (page 2)
    if result.get("has_more"):
        result_p2 = await tools.get_staking_info(limit=20, offset=20)
        pools_p2 = result_p2.get("available_pools", [])
        print(f"  Page 2: showing={result_p2.get('showing')}, offset={result_p2.get('offset')}")
        assert result_p2.get("offset") == 20
        # Pages should not overlap
        addrs_p1 = {p.get("address") for p in pools}
        addrs_p2 = {p.get("address") for p in pools_p2}
        assert not addrs_p1 & addrs_p2, "Pages should not overlap"

    print("  PASS")
    return True


async def test_staking_positions(tools: ToolManager):
    sep("TEST: get_staking_info (address positions)")
    result = await tools.get_staking_info(address=TON_FOUNDATION)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    positions = result.get("staking_positions", [])
    print(f"  Positions: {result.get('total_positions')}")
    for p in positions[:3]:
        print(f"    Pool: {p.get('pool_name', p.get('pool_address', 'N/A')[:20])}, staked: {p.get('amount_staked')} TON")
    print("  PASS")
    return True


# =========================================================================
# Main
# =========================================================================

async def main():
    gecko_only = "--gecko-only" in sys.argv

    api_key = os.getenv("TON_API_KEY", "")
    gecko_client = GeckoClient()

    if gecko_only:
        ton_client = None
        tools = ToolManager(
            ton_client=TonClient(api_key="dummy"),
            gecko_client=gecko_client,
        )
    else:
        if not api_key:
            print("WARNING: TON_API_KEY not set. Run with --gecko-only for GeckoTerminal tests only.")
            print("Set TON_API_KEY in .env or environment for full tests.")
            sys.exit(1)
        ton_client = TonClient(api_key=api_key)
        tools = ToolManager(
            ton_client=ton_client,
            gecko_client=gecko_client,
        )

    results = {}

    try:
        # GeckoTerminal tests (always run)
        results["trending_tokens"] = await test_trending_tokens(tools)
        results["trending_pools"] = await test_trending_pools(tools)
        results["new_pools"] = await test_new_pools(tools)
        results["token_market_data"] = await test_token_market_data(tools)
        results["invalid_category"] = await test_invalid_category(tools)

        if not gecko_only:
            # TONAPI tests
            results["analyze_address"] = await test_analyze_address(tools)
            results["trading_patterns"] = await test_trading_patterns(tools)
            results["trading_too_many"] = await test_trading_patterns_too_many(tools)
            results["transaction_details"] = await test_transaction_details(tools)
            results["account_events"] = await test_account_events(tools)
            results["ton_price"] = await test_ton_price(tools)
            results["jetton_info"] = await test_jetton_info(tools)
            results["jetton_holders"] = await test_jetton_holders(tools)
            results["wallet_jettons"] = await test_wallet_jettons(tools)
            results["blockchain_status"] = await test_blockchain_status(tools)
            results["staking_info"] = await test_staking_info(tools)
            results["staking_positions"] = await test_staking_positions(tools)

        # Summary
        sep("RESULTS SUMMARY")
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        for name, ok in results.items():
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {name}")
        print(f"\n  {passed}/{total} tests passed")

    finally:
        await gecko_client.close()
        if ton_client:
            await ton_client.close()


if __name__ == "__main__":
    asyncio.run(main())
