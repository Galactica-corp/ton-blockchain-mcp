import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ServerConfig:
    """Server configuration"""
    host: str = "localhost"
    port: int = 8000
    log_level: str = "INFO"
    cors_enabled: bool = True
    cors_origins: list = None


@dataclass
class TonApiConfig:
    """TON API configuration"""
    api_key: str = ""
    base_url: str = "https://tonapi.io"
    timeout: int = 30
    max_retries: int = 3
    rate_limit: int = 100  # requests per minute


@dataclass
class GeckoTerminalConfig:
    """GeckoTerminal API configuration"""
    base_url: str = "https://api.geckoterminal.com/api/v2"
    rate_limit: int = 30  # requests per minute (free tier)


@dataclass
class AnalysisConfig:
    """Analysis configuration"""
    max_transactions_analysis: int = 1000
    default_timeframe: str = "24h"
    enable_forensics: bool = True
    enable_compliance_check: bool = True
    suspicious_amount_threshold: float = 10000.0


class ConfigManager:
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "config/settings.json"
        self._load_config()

    def _load_config(self):
        """Load configuration from file or environment"""
        self.server = ServerConfig()
        self.ton_api = TonApiConfig()
        self.gecko_terminal = GeckoTerminalConfig()
        self.analysis = AnalysisConfig()

        # Load from file if exists
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
                self._update_from_dict(config_data)

        # Override with environment variables
        self._load_from_env()

    def _update_from_dict(self, config_data: Dict[str, Any]):
        """Update configuration from dictionary"""
        if "server" in config_data:
            server_data = config_data["server"]
            for key, value in server_data.items():
                if hasattr(self.server, key):
                    setattr(self.server, key, value)

        if "ton_api" in config_data:
            api_data = config_data["ton_api"]
            for key, value in api_data.items():
                if hasattr(self.ton_api, key):
                    setattr(self.ton_api, key, value)

        if "gecko_terminal" in config_data:
            gecko_data = config_data["gecko_terminal"]
            for key, value in gecko_data.items():
                if hasattr(self.gecko_terminal, key):
                    setattr(self.gecko_terminal, key, value)

        if "analysis" in config_data:
            analysis_data = config_data["analysis"]
            for key, value in analysis_data.items():
                if hasattr(self.analysis, key):
                    setattr(self.analysis, key, value)

    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Server config
        self.server.host = os.getenv("MCP_HOST", self.server.host)
        self.server.port = int(os.getenv("MCP_PORT", self.server.port))
        self.server.log_level = os.getenv("LOG_LEVEL", self.server.log_level)

        # TON API config
        self.ton_api.api_key = os.getenv("TON_API_KEY", self.ton_api.api_key)
        self.ton_api.base_url = os.getenv("TON_API_URL", self.ton_api.base_url)
        self.ton_api.timeout = int(os.getenv("TON_API_TIMEOUT", self.ton_api.timeout))

        # GeckoTerminal config
        self.gecko_terminal.base_url = os.getenv("GECKO_API_URL", self.gecko_terminal.base_url)

        # Analysis config
        self.analysis.max_transactions_analysis = int(os.getenv("MAX_TX_ANALYSIS", self.analysis.max_transactions_analysis))
        self.analysis.enable_forensics = os.getenv("ENABLE_FORENSICS", "true").lower() == "true"

    def save_config(self):
        """Save current configuration to file"""
        config_data = {
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "log_level": self.server.log_level,
                "cors_enabled": self.server.cors_enabled
            },
            "ton_api": {
                "base_url": self.ton_api.base_url,
                "timeout": self.ton_api.timeout,
                "max_retries": self.ton_api.max_retries,
                "rate_limit": self.ton_api.rate_limit
            },
            "gecko_terminal": {
                "base_url": self.gecko_terminal.base_url,
                "rate_limit": self.gecko_terminal.rate_limit
            },
            "analysis": {
                "max_transactions_analysis": self.analysis.max_transactions_analysis,
                "default_timeframe": self.analysis.default_timeframe,
                "enable_forensics": self.analysis.enable_forensics,
                "enable_compliance_check": self.analysis.enable_compliance_check,
                "suspicious_amount_threshold": self.analysis.suspicious_amount_threshold
            }
        }

        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f, indent=2)

    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return {
            "server": self.server.__dict__,
            "ton_api": self.ton_api.__dict__,
            "gecko_terminal": self.gecko_terminal.__dict__,
            "analysis": self.analysis.__dict__
        }
