from pathlib import Path

from pydantic_settings import BaseSettings


class MCPSettings(BaseSettings):
    
    # Storage configuration
    STORAGE_PATH: Path = Path("./storage")
    STORAGE_FILE: str = "confirmed_reservations.txt"
    
    # MCP Server configuration
    MCP_ENABLED: bool = True
    MCP_TIMEOUT: int = 30
    MCP_SERVER_COMMAND: str = "npx"
    MCP_SERVER_ARGS: list = [
        "@modelcontextprotocol/server-filesystem",
        "./storage"
    ]
    
    # File format configuration
    ENTRY_SEPARATOR: str = " | "
    DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    
    class Config:
        env_prefix = "MCP_"
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields from .env file


_settings: MCPSettings | None = None


def get_mcp_settings() -> MCPSettings:
    global _settings
    if _settings is None:
        _settings = MCPSettings()
    return _settings
