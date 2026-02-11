import contextlib
import logging
import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends, Body, Path, Header
from mcp.server.fastmcp import FastMCP
from tonmcp.ton_client import TonClient
from tonmcp.prompts import PromptManager
from tonmcp.tools import ToolManager, base64url_to_hex
from typing import Any

load_dotenv()

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Create FastMCP server instance with streamable HTTP support
tmcp = FastMCP("TON MCP Server", stateless_http=True, json_response=True)

# --- Test constants for TON MCP tool endpoints ---
TON_COIN_ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c"  # TON coin address on TON Blockchain
TEST_WALLET_ADDRESS = "UQBXbfJhkqlCpDXPn_x5uXDR_cqC7xfjx3jhwx5DOO1DWqZn"  # Wallet address for analyze_trading_patterns
TEST_JETTON_ADDRESS = "EQAvlWFDxGF2lXm67y4yzC17wYKD9A0guwPkMs1gOsM__NOT"  # Jetton address for get_jetton_price
# These can be used in test scripts or for manual endpoint testing

class TonMcpServer:
    def __init__(self, api_key: str, base_url: str = " https://tonapi.io"):
        logger.debug("Initializing TonMcpServer with API key and base_url=%s", base_url)
        self.api_key = api_key
        self.ton_client = TonClient(api_key, base_url)
        self.prompt_manager = PromptManager()
        self.tool_manager = ToolManager(self.ton_client)
        self._register_tools()
        self._register_prompts()

    def _register_tools(self):
        logger.debug("Registering tools...")
        @tmcp.tool(
            description="Analyze a TON address for its balance, jetton holdings, NFTs, and recent activity. Optionally performs deep forensic analysis if deep_analysis is True. Use for questions about account overview, holdings, or activity."
        )
        async def analyze_address(address: str, deep_analysis: bool = False) -> Any:
            """Example: analyze_address(address='UQ...youraddress...', deep_analysis=True)
            Analyze a TON address including balance, transactions, and patterns.
            """
            logger.debug(f"analyze_address called with address={address}, deep_analysis={deep_analysis}")
            result = await self.tool_manager.analyze_address(address=address, deep_analysis=deep_analysis)
            logger.debug(f"analyze_address result: {result}")
            return result

        @tmcp.tool(
            description="Get details and analysis for a specific TON blockchain transaction by its hash. Use for questions about a particular transaction, its participants, value, or type."
        )
        async def get_transaction_details(tx_hash: str) -> Any:
            """Example: get_transaction_details(tx_hash='14069dfe829c040e81dd983a0022eec38b45505591a538c47c032364fa0bccb9')
            Get details for a transaction hash.
            """
            return await self.tool_manager.get_transaction_details(tx_hash=tx_hash)

        @tmcp.tool(
            description="Find trending tokens, pools, or accounts on the TON blockchain for a given timeframe and category. Use for questions about what's hot, trending, or popular on TON."
        )
        async def find_hot_trends(timeframe: str = "1h", category: str = "tokens") -> Any:
            """Example: find_hot_trends(timeframe='1h', category='tokens')
            Find hot trends on TON.
            """
            return await self.tool_manager.find_hot_trends(timeframe=timeframe, category=category)

        @tmcp.tool(
            description="Analyze trading patterns for a TON address over a specified timeframe. Use for questions about trading activity, frequency, jetton transfers, or DEX swaps for an account."
        )
        async def analyze_trading_patterns(address: str, timeframe: str = "24h") -> Any:
            """Example: analyze_trading_patterns(address='UQ...youraddress...', timeframe='24h')\nAnalyze trading patterns for an address."""
            return await self.tool_manager.analyze_trading_patterns(address=address, timeframe=timeframe)

        @tmcp.tool(
            description="Get the current real-time TON price in the specified currency (default: USD) and recent price changes."
        )
        async def get_ton_price(currency: str = "usd") -> Any:
            """Example: get_ton_price(currency='usd')\nGet the current real-time TON price in the specified currency (default: USD) and recent price changes."""
            return await self.tool_manager.get_ton_price(currency=currency)

        @tmcp.tool(
            description="Get the current price and recent changes for specified jetton tokens (not TON) in the given currency. Provide a list of jetton master addresses as tokens."
        )
        async def get_jetton_price(tokens: list, currency: str = "usd") -> Any:
            """Example: get_jetton_price(tokens=['0:dfbbf59e9b306b86194a2441f4f80b51bbd68253290549bd76a7165c0082ae80'], currency='usd')\nGet the current price and recent changes for specified jetton tokens (not TON) in the given currency."""
            return await self.tool_manager.get_jetton_price(tokens=tokens, currency=currency)

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

# Ensure tools/prompts are registered for FastAPI
TonMcpServer(api_key=os.getenv("TON_API_KEY", "changeme"))

def get_api_key(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Forbidden")
    token = authorization.split(" ", 1)[1]
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return token


# Lifespan context manager for the streamable HTTP session manager
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with tmcp.session_manager.run():
        yield


app = FastAPI(title="TON MCP Remote Server", docs_url=None, redoc_url=None, lifespan=lifespan)

# Mount the MCP streamable HTTP transport at /mcp
# Set internal path to "/" so the full endpoint is /mcp (not /mcp/mcp)
tmcp.settings.streamable_http_path = "/"
app.mount("/mcp", tmcp.streamable_http_app())

@app.get("/tools", dependencies=[Depends(get_api_key)])
async def list_tools():
    # MCP-compliant tool list
    tools = []
    for tool in tmcp._tool_manager.list_tools():
        # Extract usage example from the first line of the docstring, if present
        usage_example = None
        if tool.fn.__doc__:
            first_line = tool.fn.__doc__.strip().split("\n")[0]
            if 'example:' in first_line.lower():
                usage_example = first_line.strip()
        tools.append({
            "id": tool.name,
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,  # This may need to be MCP schema compliant
            "usage_example": usage_example
        })
    return {"tools": tools}

@app.post("/tools/{tool_id}/call", dependencies=[Depends(get_api_key)])
async def call_tool(tool_id: str = Path(...), body: dict = Body(...)):
    # Find the tool by ID
    tool = next((t for t in tmcp._tool_manager.list_tools() if t.name == tool_id), None)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    # Call the tool with provided arguments
    try:
        result = await tool.run(body)
        return {"result": result}
    except Exception as e:
        logger.exception(f"Error calling tool {tool_id}")
        raise HTTPException(status_code=500, detail=str(e))

# Optionally, health check
@app.get("/healthz")
def health():
    return {"status": "ok"}

# CLI entry point
def main():
    api_key = os.getenv("TON_API_KEY")
    logger.debug(f"Starting main with TON_API_KEY={api_key}")
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
        # Run FastAPI app with streamable HTTP MCP endpoint + REST API
        import uvicorn
        uvicorn.run("tonmcp.mcp_server:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
    else:
        main()