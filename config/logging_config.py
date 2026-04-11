import logging
import sys
from typing import Optional

from config.settings import LOGS_DIR, settings


def setup_logging(
    level: Optional[str] = None,
    quiet: Optional[bool] = None,
    log_to_file: bool = False,
    filename: Optional[str] = None
) -> None:
    log_level = level or settings.log_level
    is_quiet = quiet if quiet is not None else settings.quiet_mode    
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)    
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)    
    root_logger.handlers.clear()    
    if settings.debug_mode:
        # Detailed format for debugging
        fmt = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    else:
        # Simple format for production
        fmt = '%(asctime)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(fmt, datefmt='%Y-%m-%d %H:%M:%S')
    
    if not is_quiet:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    if log_to_file:
        LOGS_DIR.mkdir(exist_ok=True)
        log_file = LOGS_DIR / (filename or f"{settings.app_name.lower().replace(' ', '_')}.log")
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Silence noisy third-party libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('deeplake').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def disable_all_logging():
    logging.disable(logging.CRITICAL)


def enable_logging():
    logging.disable(logging.NOTSET)


setup_logging()
