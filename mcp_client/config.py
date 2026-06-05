import logging
from pathlib import Path
from typing import Union

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class MCPSettings(BaseSettings):

    # Storage configuration
    STORAGE_PATH: Path = Path("./storage")
    STORAGE_FILE: str = "confirmed_reservations.txt"

    @field_validator('STORAGE_PATH', mode='before')
    @classmethod
    def convert_to_path(cls, v: Union[str, Path]) -> Path:
        if isinstance(v, str):
            return Path(v)
        return v

    # MCP Server configuration
    MCP_ENABLED: bool = True
    MCP_TIMEOUT: int = 30
    MCP_SERVER_COMMAND: str = "npx"
    MCP_SERVER_ARGS: list = []  # Default empty, will be populated

    def model_post_init(self, __context):
        """Called after model initialization and validation."""
        if not self.MCP_SERVER_ARGS:
            storage_absolute = self.STORAGE_PATH.absolute()
            self.MCP_SERVER_ARGS = [
                "@modelcontextprotocol/server-filesystem",
                str(storage_absolute)
            ]
            logger.info(f"MCP Server will use storage path: {storage_absolute}")
    
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
