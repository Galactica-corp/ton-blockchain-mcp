"""
TON Blockchain MCP Server.
Exposes 15 tools for comprehensive TON blockchain exploration.
Supports STDIO, Streamable HTTP, and FastAPI transports.
"""
import contextlib
import logging
import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends, Body, Path, Header
from mcp.server.fastmcp import FastMCP
from tonmcp.ton_client import TonClient
from tonmcp.gecko_client import GeckoClient
from tonmcp.prompts import PromptManager
from tonmcp.tools import ToolManager
from typing import Any, Optional

load_dotenv()

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Create FastMCP server instance
tmcp = FastMCP("TON MCP Server", stateless_http=True, json_response=True)


class TonMcpServer:
    _instance: Optional["TonMcpServer"] = None

    def __init__(self, api_key: str, base_url: str = "https://tonapi.io"):
        logger.debug("Initializing TonMcpServer with base_url=%s", base_url)
        self.ton_client = TonClient(api_key, base_url)
        self.gecko_client = GeckoClient()
        self.prompt_manager = PromptManager()

        max_events = int(os.getenv("MAX_TX_ANALYSIS", "1000"))
        self.tool_manager = ToolManager(
            ton_client=self.ton_client,
            gecko_client=self.gecko_client,
            max_events=max_events,
        )

        self._register_tools()
        self._register_prompts()
        TonMcpServer._instance = self

    async def cleanup(self):
        await self.ton_client.close()
        await self.gecko_client.close()

    def _register_tools(self):
        logger.debug("Registering tools...")

        # 1. analyze_address
        @tmcp.tool(
            description=(
                "Analyze a TON address: balance in TON and USD, jetton holdings with prices, "
                "NFT count, and recent activity sample. Set deep_analysis=True for event pattern analysis."
            )
        )
        async def analyze_address(address: str, deep_analysis: bool = False) -> Any:
            """Analyze a TON address including balance, tokens, NFTs, and activity."""
            return await self.tool_manager.analyze_address(address=address, deep_analysis=deep_analysis)

        # 2. get_transaction_details
        @tmcp.tool(
            description=(
                "Get details and parsed actions for a TON transaction by its hash. "
                "Returns high-level actions (JettonTransfer, JettonSwap, NftTransfer, etc.) "
                "instead of raw blockchain data."
            )
        )
        async def get_transaction_details(tx_hash: str) -> Any:
            """Get parsed transaction details by hash."""
            return await self.tool_manager.get_transaction_details(tx_hash=tx_hash)

        # 3. find_hot_trends
        @tmcp.tool(
            description=(
                "Find trending tokens or pools on TON. "
                "Category 'tokens' returns deduplicated trending tokens sorted by 24h volume. "
                "Category 'pools' returns trending trading pools. "
                "Category 'new_pools' returns recently created pools. "
                "Data sourced from GeckoTerminal with real volume and activity metrics."
            )
        )
        async def find_hot_trends(category: str = "tokens") -> Any:
            """Find trending tokens/pools on TON."""
            return await self.tool_manager.find_hot_trends(category=category)

        # 4. analyze_trading_patterns
        @tmcp.tool(
            description=(
                "Analyze trading patterns for a TON address over a specified timeframe "
                "(e.g., '24h', '7d', '30d'). Fetches ALL events in the period with pagination. "
                "Returns full analysis or error if the timeframe contains too many events."
            )
        )
        async def analyze_trading_patterns(address: str, timeframe: str = "24h") -> Any:
            """Analyze trading patterns for an address."""
            return await self.tool_manager.analyze_trading_patterns(address=address, timeframe=timeframe)

        # 5. get_ton_price
        @tmcp.tool(
            description="Get the current real-time TON price in the specified currency (default: USD) and recent price changes."
        )
        async def get_ton_price(currency: str = "usd") -> Any:
            """Get current TON price."""
            return await self.tool_manager.get_ton_price(currency=currency)

        # 6. get_jetton_price
        @tmcp.tool(
            description="Get current prices for specified jetton tokens by their master addresses."
        )
        async def get_jetton_price(tokens: list, currency: str = "usd") -> Any:
            """Get jetton token prices."""
            return await self.tool_manager.get_jetton_price(tokens=tokens, currency=currency)

        # 7. get_jetton_info
        @tmcp.tool(
            description=(
                "Get detailed information about a jetton (token): name, symbol, total supply, "
                "holders count, verification status, mintability, current price, and social links."
            )
        )
        async def get_jetton_info(jetton_address: str) -> Any:
            """Get detailed jetton metadata and price."""
            return await self.tool_manager.get_jetton_info(jetton_address=jetton_address)

        # 8. get_jetton_holders
        @tmcp.tool(
            description=(
                "Get the top holders of a jetton (token) with human-readable balances. "
                "Shows owner addresses and amounts. Useful for analyzing token distribution."
            )
        )
        async def get_jetton_holders(jetton_address: str, limit: int = 100) -> Any:
            """Get top holders of a jetton."""
            return await self.tool_manager.get_jetton_holders(jetton_address=jetton_address, limit=limit)

        # 9. resolve_ton_domain
        @tmcp.tool(
            description="Resolve a .ton domain name to its address and records. Use when given a domain like 'alice.ton'."
        )
        async def resolve_ton_domain(domain: str) -> Any:
            """Resolve .ton domain to address."""
            return await self.tool_manager.resolve_ton_domain(domain=domain)

        # 10. get_wallet_jettons
        @tmcp.tool(
            description=(
                "Get all jetton (token) holdings for a wallet address with current USD prices. "
                "Returns sorted portfolio with total value."
            )
        )
        async def get_wallet_jettons(address: str) -> Any:
            """Get wallet's jetton portfolio with prices."""
            return await self.tool_manager.get_wallet_jettons(address=address)

        # 11. get_blockchain_status
        @tmcp.tool(
            description="Get current TON blockchain status: latest masterchain block, validator count, and network time."
        )
        async def get_blockchain_status() -> Any:
            """Get TON blockchain network status."""
            return await self.tool_manager.get_blockchain_status()

        # 12. get_token_market_data
        @tmcp.tool(
            description=(
                "Get market data for a TON token from GeckoTerminal: price, 24h volume, "
                "FDV, market cap, liquidity, and top trading pools."
            )
        )
        async def get_token_market_data(token_address: str) -> Any:
            """Get token market data from GeckoTerminal."""
            return await self.tool_manager.get_token_market_data(token_address=token_address)

        # 13. get_account_events
        @tmcp.tool(
            description=(
                "Get recent events (transactions) for a TON address with pagination. "
                "Returns up to 'limit' events per page. Pass 'before_lt' from previous response's "
                "'next_before_lt' to get the next page."
            )
        )
        async def get_account_events(address: str, limit: int = 25, before_lt: int = None) -> Any:
            """Get paginated event history for an address."""
            return await self.tool_manager.get_account_events(address=address, limit=limit, before_lt=before_lt)

        # 14. get_staking_info
        @tmcp.tool(
            description=(
                "Get staking information. Without address: lists all available staking pools with APY. "
                "With address: shows the staking positions for that specific wallet."
            )
        )
        async def get_staking_info(address: str = None) -> Any:
            """Get staking pools or positions."""
            return await self.tool_manager.get_staking_info(address=address)

        # 15. get_nft_info
        @tmcp.tool(
            description=(
                "Get information about an NFT item or collection by address. "
                "Automatically detects whether the address is an NFT item or collection."
            )
        )
        async def get_nft_info(nft_address: str) -> Any:
            """Get NFT item or collection info."""
            return await self.tool_manager.get_nft_info(nft_address=nft_address)

    def _register_prompts(self):
        logger.debug("Registering prompts...")

        @tmcp.prompt()
        async def trading_analysis(**kwargs) -> str:
            return await self.prompt_manager.get_trading_analysis_prompt(**kwargs)

        @tmcp.prompt()
        async def forensics_investigation(**kwargs) -> str:
            return await self.prompt_manager.get_forensics_prompt(**kwargs)

        @tmcp.prompt()
        async def trend_analysis(**kwargs) -> str:
            return await self.prompt_manager.get_trend_analysis_prompt(**kwargs)


API_KEY = os.getenv("API_KEY", "changeme")

# Ensure tools/prompts are registered
TonMcpServer(api_key=os.getenv("TON_API_KEY", "changeme"))


def get_api_key(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Forbidden")
    token = authorization.split(" ", 1)[1]
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return token


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with tmcp.session_manager.run():
        yield
    # Cleanup HTTP sessions on shutdown
    if TonMcpServer._instance:
        await TonMcpServer._instance.cleanup()


app = FastAPI(title="TON MCP Remote Server", docs_url=None, redoc_url=None, lifespan=lifespan)

# Mount MCP streamable HTTP transport at /mcp
tmcp.settings.streamable_http_path = "/"
app.mount("/mcp", tmcp.streamable_http_app())


@app.get("/tools", dependencies=[Depends(get_api_key)])
async def list_tools():
    tools = []
    for tool in tmcp._tool_manager.list_tools():
        tools.append({
            "id": tool.name,
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        })
    return {"tools": tools}


@app.post("/tools/{tool_id}/call", dependencies=[Depends(get_api_key)])
async def call_tool(tool_id: str = Path(...), body: dict = Body(...)):
    tool = next((t for t in tmcp._tool_manager.list_tools() if t.name == tool_id), None)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    try:
        result = await tool.run(body)
        return {"result": result}
    except Exception as e:
        logger.exception(f"Error calling tool {tool_id}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/healthz")
def health():
    return {"status": "ok"}


# CLI entry point
def main():
    api_key = os.getenv("TON_API_KEY")
    if not api_key:
        raise ValueError("TON_API_KEY environment variable is required")
    TonMcpServer(api_key)

    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    logger.debug(f"Running FastMCP server with transport={transport}...")
    tmcp.run(transport=transport)


if __name__ == "__main__":
    if "runserver" in sys.argv:
        import uvicorn
        uvicorn.run("tonmcp.mcp_server:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
    else:
        main()
