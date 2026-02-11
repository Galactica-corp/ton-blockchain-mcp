# TON BLOCKCHAIN MCP 

A Model Context Protocol (MCP) server for natural language interaction with the [TON blockchain](http://ton.org/).

![TON Blockchain MCP Cover](docs/cover_image.png)

## Features

- **Natural Language Processing**: Understand complex blockchain queries in plain English
- **Trading Analysis**: Analyze trading patterns, profitability, and strategies
- **Hot Trends Detection**: Find trending tokens, active pools, and high-activity accounts
- **Forensics & Compliance**: Conduct blockchain investigations and compliance checks
- **Real-time Data**: Access live TON blockchain data through TON API

## Quick Start

### Prerequisites

- Python 3.10+
- TON API key from [TONAPI](https://tonconsole.com/tonapi)

### Environment Configuration (.env)

To securely provide sensitive configuration (such as your TON API key), create a `.env` file in the project root directory. This file will be loaded automatically if present.

**Example `.env` file:**

```
TON_API_KEY=YOUR_TON_API_KEY
```

### Installation

1. Clone the repository:
```bash
git clone https://github.com/devonmojito/ton-blockchain-mcp.git
cd ton-blockchain-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

---

## Using TON MCP Server with Claude Desktop

You can easily use this MCP server with Claude Desktop for natural language blockchain queries. Below are some example use cases:

**Scam Detection Example:**

![Scam Detection Example](docs/example_scam_detection.png)

**Analyze Address Example:**

![Analyze Address Example](docs/example_analyze_address.png)

**Get Transaction Details Example:**

![Get Transaction Details Example](docs/example_get_transaction_details.png)

**Analyze Trading Patterns Example:**

![Analyze Trading Patterns Example](docs/example_analyze_trading_patterns.png)

### Claude Desktop Configuration Example

To use this MCP server with Claude Desktop (STDIO transport), add the following to your Claude Desktop config.
Replace paths with your own.

```json
{
    "mcpServers": {
        "ton-mcp-server": {
            "command": "/path/to/ton-blockchain-mcp/venv/bin/python",
            "args": ["-m", "tonmcp.mcp_server"],
            "cwd": "/path/to/ton-blockchain-mcp/src",
            "env": {
                "PYTHONPATH": "/path/to/ton-blockchain-mcp/src"
            },
            "stdio": true
        }
    }
}
```

For remote/HTTP connections, use the Streamable HTTP transport instead (see below).

---

### Running as HTTP Server (Streamable HTTP)

The server supports the [Streamable HTTP](https://modelcontextprotocol.io) transport — the recommended MCP transport for network-based and production deployments.

**Standalone (FastMCP built-in server):**

```bash
python -m tonmcp.mcp_server --transport streamable-http
```

MCP clients connect to `http://localhost:8000/mcp`.

**As a FastAPI app (MCP + REST API):**

```bash
# via uvicorn
PYTHONPATH=src uvicorn tonmcp.mcp_server:app --host 0.0.0.0 --port 8000

# or via the built-in runner
python -m tonmcp.mcp_server runserver
```

This exposes:
- `/mcp` — MCP Streamable HTTP endpoint (for MCP clients)
- `/tools` — REST API: list available tools (requires `Authorization: Bearer <API_KEY>`)
- `/tools/{tool_id}/call` — REST API: call a tool (requires auth)
- `/healthz` — health check

**Docker:**

```bash
docker-compose up
```

The server will be available at `http://localhost:8000`.

---

### Natural Language Examples

- "What's the balance of address EQD1234...?"
- "Find hot trading pairs in the last hour"
- "Analyze trading patterns for this wallet"
- "Show suspicious activity for address ABC"
- "Trace money flow from this address"


## MCP Tools & System Prompts Documentation

### Tools

#### analyze_address
Analyze a TON address for its balance, jetton holdings, NFTs, and recent activity. Optionally performs deep forensic analysis if `deep_analysis` is True. Use for questions about account overview, holdings, or activity.

**Parameters:**
- `address` (str): TON address to analyze
- `deep_analysis` (bool, optional): Enable deep forensic analysis

#### get_transaction_details
Get details and analysis for a specific TON blockchain transaction by its hash. Use for questions about a particular transaction, its participants, value, or type.

**Parameters:**
- `tx_hash` (str): Transaction hash

#### find_hot_trends
Find trending tokens, pools, or accounts on the TON blockchain for a given timeframe and category. Use for questions about what's hot, trending, or popular on TON.

**Parameters:**
- `timeframe` (str, optional): Time period (e.g., 1h, 24h, 7d)
- `category` (str, optional): Type of trends (tokens, pools, accounts)

#### analyze_trading_patterns
Analyze trading patterns for a TON address over a specified timeframe. Use for questions about trading activity, frequency, jetton transfers, or DEX swaps for an account.

**Parameters:**
- `address` (str): TON address
- `timeframe` (str, optional): Time period (e.g., 24h)

#### get_ton_price
Get the current real-time TON price in the specified currency (default: USD) and recent price changes. Use this tool whenever you need the latest TON price for calculations, analysis, or reporting.

**Parameters:**
- `currency` (str, optional): The fiat or crypto currency to get the TON price in (default: 'usd').

#### get_jetton_price
Get the current price and recent changes for specified jetton tokens (not TON) in the given currency. Provide a list of jetton master addresses as tokens. Use this tool to fetch real-time prices for any token except TON.

**Parameters:**
- `tokens` (list of str): List of jetton master addresses to get prices for (excluding 'ton').
- `currency` (str, optional): The fiat or crypto currency to get the price in (default: 'usd').

### System Prompts

- `trading_analysis`: Generate trading analysis prompts
- `forensics_investigation`: Generate forensics prompts
- `trend_analysis`: Generate trend analysis prompts

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue on GitHub 

**⚠️ WARNING: This project is in Beta. Do not trust any numbers provided by the LLM model. Nothing in this project constitutes financial advice. Use at your own risk.**

