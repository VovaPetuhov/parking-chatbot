import logging

import uvicorn

from config.logging_config import setup_logging
from config.settings import settings

setup_logging(quiet=False)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting Parking Chatbot API Server")
    host = getattr(settings, 'api_host', '0.0.0.0')
    port = getattr(settings, 'api_port', 8000)
    reload = getattr(settings, 'api_reload', True)
    logger.info(f"API Host: {host}")
    logger.info(f"API Port: {port}")
    logger.info(f"Hot Reload: {reload}")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info("")
    logger.info(f"API will be available at: http://{host}:{port}")
    logger.info(f"Swagger docs: http://{host}:{port}/docs")
    logger.info(f"ReDoc docs: http://{host}:{port}/redoc")
    
    try:
        uvicorn.run(
            "api.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level=settings.log_level.lower()
        )
    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        raise


if __name__ == "__main__":
    main()
