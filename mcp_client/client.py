
import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ListRootsRequest, ListRootsResult, Root
from pydantic import AnyUrl

from mcp_client.config import MCPSettings, get_mcp_settings

logger = logging.getLogger(__name__)


class CustomClientSession(ClientSession):
    """
    Extended ClientSession that handles server requests.
    The MCP Filesystem Server can send requests to the client
    (e.g., roots/list). This class handles those requests to
    prevent timeout errors.
    """

    def __init__(self, *args, storage_path: Path, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage_path = storage_path.absolute()
        logger.info(f"CustomClientSession initialized with storage_path={self.storage_path}")

    async def _received_request(self, responder):
        """
        Handle requests from MCP server.
        Currently handles:
        - roots/list: Provides list of allowed directories
        """
        try:
            request = responder.request
            logger.info(f"Received request from MCP server: {type(request).__name__}")
            actual_request = request.root if hasattr(request, 'root') else request
            logger.info(f"Actual request type: {type(actual_request).__name__}")

            # Check if this is a ListRootsRequest
            if isinstance(actual_request, ListRootsRequest):
                logger.info(f"Handling ListRootsRequest from MCP server, providing root: {self.storage_path}")

                # Provide storage directory as root
                # Convert to absolute path and create proper file:// URI
                storage_uri = self.storage_path.as_uri()
                logger.info(f"Storage URI: {storage_uri}")

                roots = [
                    Root(
                        uri=AnyUrl(storage_uri),
                        name="storage"
                    )
                ]

                result = ListRootsResult(roots=roots)
                await responder.respond(result)

                logger.info(f"Successfully provided {len(roots)} root(s) to MCP server")
                return

            # Fallback to base class for unknown requests
            logger.warning(f"Unknown request type: {type(actual_request).__name__}, delegating to parent")
            await super()._received_request(responder)
        except Exception as e:
            logger.error(f"Error handling request from MCP server: {e}", exc_info=True)
            raise


class MCPFilesystemClient:
    """
    Client for MCP Filesystem Server
    
    Provides high-level interface for writing reservation data
    to file storage using Model Context Protocol.
    
    Features:
    - Async communication with MCP server via stdio
    - Error handling and retries
    - Input validation and sanitization
    - Structured logging
    """
    
    def __init__(self, settings: Optional[MCPSettings] = None):
        self.settings = settings or get_mcp_settings()

        self.settings.STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage directory verified: {self.settings.STORAGE_PATH.absolute()}")

        self.server_params = StdioServerParameters(
            command=self.settings.MCP_SERVER_COMMAND,
            args=self.settings.MCP_SERVER_ARGS,
            env=None
        )
        self._session_lock = asyncio.Lock()
        logger.info(f"MCP Client initialized: storage={self.settings.STORAGE_PATH}")
        logger.info(
            f"MCP Server command: {self.settings.MCP_SERVER_COMMAND} {' '.join(self.settings.MCP_SERVER_ARGS)}"
        )
    
    @asynccontextmanager
    async def _get_session(self):
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with CustomClientSession(
                    read, 
                    write,
                    storage_path=self.settings.STORAGE_PATH
                ) as session:
                    await asyncio.wait_for(
                        session.initialize(),
                        timeout=self.settings.MCP_TIMEOUT
                    )

                    logger.debug("MCP session established")
                    yield session

        except asyncio.TimeoutError:
            logger.error("MCP session initialization timeout")
            raise
        except Exception as e:
            logger.error(f"MCP session error: {e}", exc_info=True)
            raise
    
    def _sanitize_value(self, value: str) -> str:        
        sanitized = re.sub(r'[\n\r\|]', '', value)
        sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)
        return sanitized.strip()
    
    def _format_reservation_entry(
        self,
        name: str,
        surname: str,
        car_plate: str,
        start_time: str,
        end_time: str,
        approval_time: datetime
    ) -> str:
        """
        Format reservation data as file entry
        Format: Name | Car Number | Period | Approval Time
        Args:
            name: User's first name
            surname: User's last name
            car_plate: Car license plate
            start_time: Reservation start date/time
            end_time: Reservation end date/time
            approval_time: When reservation was approved
        Returns:
            Formatted entry string with newline
        """
        full_name = self._sanitize_value(f"{name} {surname}")
        car_plate_clean = self._sanitize_value(car_plate)
        period = f"{start_time} to {end_time}"
        approval_str = approval_time.strftime(self.settings.DATE_FORMAT)        
        sep = self.settings.ENTRY_SEPARATOR
        entry = f"{full_name}{sep}{car_plate_clean}{sep}{period}{sep}{approval_str}\n"
        
        return entry
    
    async def append_to_file(
        self,
        filename: str,
        content: str
    ) -> bool:
        """
        Append content to file using MCP server
        Args:
            filename: Name of file in storage directory
            content: Content to append
        Returns:
            True if successful, False otherwise
        """
        if not self.settings.MCP_ENABLED:
            logger.warning("MCP is disabled, skipping file write")
            return False
        
        try:
            async with self._session_lock:
                async with self._get_session() as session:
                    try:
                        logger.info(f"MCP: Attempting to read existing file: {filename}")
                        read_result = await session.call_tool(
                            "read_file",
                            arguments={
                                "path": filename
                            }
                        )

                        # Check if read was successful
                        if read_result.isError:
                            logger.info(f"MCP: File doesn't exist yet, will create new")
                            existing_content = ""
                        else:
                            existing_content = read_result.content[0].text if read_result.content else ""
                            logger.info(f"MCP: Read {len(existing_content)} bytes from existing file")
                    except Exception as e:
                        logger.info(f"MCP: No existing file or read error: {e}")
                        existing_content = ""
                    
                    new_content = existing_content + content
                    logger.info(f"MCP: Writing to file with path='{filename}' (relative to storage root)")
                    logger.info(f"MCP: Content length={len(new_content)} bytes")

                    result = await session.call_tool(
                        "write_file",
                        arguments={
                            "path": filename,
                            "content": new_content
                        }
                    )

                    logger.info(f"MCP: Write result={result}")
                    
                    logger.info(
                        f"MCP write successful: {filename}, "
                        f"size={len(content)} bytes"
                    )
                    return True
                    
        except Exception as e:
            logger.error(
                f"MCP write failed for {filename}: {e}",
                exc_info=True
            )
            return False
    
    async def write_confirmed_reservation(
        self,
        name: str,
        surname: str,
        car_plate: str,
        start_time: str,
        end_time: str,
        approval_time: Optional[datetime] = None
    ) -> bool:
        """
        Write confirmed reservation to file via MCP
        High-level method that:
        1. Formats reservation data
        2. Validates inputs
        3. Writes to file via MCP server
        Args:
            name: User's first name
            surname: User's last name
            car_plate: Car license plate number
            start_time: Reservation start (string)
            end_time: Reservation end (string)
            approval_time: When approved (defaults to now)   
        Returns:
            True if successfully written, False otherwise
        """
        if approval_time is None:
            approval_time = datetime.now()
        
        entry = self._format_reservation_entry(
            name=name,
            surname=surname,
            car_plate=car_plate,
            start_time=start_time,
            end_time=end_time,
            approval_time=approval_time
        )
        
        success = await self.append_to_file(
            filename=str(self.settings.STORAGE_PATH / self.settings.STORAGE_FILE),
            content=entry
        )
        
        if success:
            logger.info(
                f"Reservation persisted: {car_plate} "
                f"({name} {surname})"
            )
        else:
            logger.error(
                f"Failed to persist reservation: {car_plate}"
            )
        
        return success


_mcp_client: Optional[MCPFilesystemClient] = None


def get_mcp_client() -> MCPFilesystemClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPFilesystemClient()
    return _mcp_client
