import logging
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from config.settings import settings

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(
    name="X-Admin-API-Key",
    auto_error=True,
    description="API key for administrative endpoints authentication"
)


async def verify_admin_api_key(
    api_key: Annotated[str, Security(API_KEY_HEADER)]
) -> str:
    """
    Verify admin API key for administrative endpoints.
    
    This dependency should be used on all admin routes that require
    authentication. It validates the API key provided in the X-Admin-API-Key
    header against the configured admin key.
    
    Args:
        api_key: API key from the request header
        
    Returns:
        str: The validated API key (for potential logging purposes)
        
    Raises:
        HTTPException: 
            - 500 if admin API key is not configured
            - 403 if provided API key is invalid or missing
    """
    if not settings.admin_api_key:
        logger.error(
            "SECURITY ERROR: Admin API key not configured in settings! "
            "Set ADMIN_API_KEY environment variable."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin authentication not configured. Contact system administrator."
        )
    
    if api_key != settings.admin_api_key:
        logger.warning(
            f"SECURITY ALERT: Invalid admin API key attempt. "
            f"Key prefix: {api_key[:8] if len(api_key) >= 8 else '***'}..."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key. Access denied."
        )
    
    logger.info(
        f"Admin authenticated successfully with key ending: "
        f"...{api_key[-4:] if len(api_key) >= 4 else '***'}"
    )
    
    return api_key
