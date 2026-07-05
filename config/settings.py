from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"


class Settings(BaseSettings):
    """Application configuration from environment variables"""
    
    # OpenAI Configuration
    openai_api_key: str
    openai_model_name: str = "gpt-4o-mini"
    openai_temperature: float = 0.0
    max_tokens: int = 1000
    data_extraction_model: str = "gpt-4o-mini"
    
    # DeepLake Configuration
    deeplake_token: Optional[str] = None
    deeplake_org_id: Optional[str] = None
    deeplake_dataset_path: str = "./data/deeplake_storage"
    
    # Application Settings
    app_name: str = "Parking Reservation Chatbot"
    app_version: str = "1.0.0"
    debug_mode: bool = False
    log_level: str = "INFO"
    quiet_mode: bool = False  # Disable all logging output
    
    # RAG Settings
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k_results: int = 5
    similarity_threshold: float = 0.5
    
    # Guardrails Settings
    enable_pii_detection: bool = True
    enable_sensitive_data_filter: bool = True
    pii_score_threshold: float = 0.5
    
    # Parking Information
    parking_name: str = "Central City Parking"
    parking_address: str = "123 Main Street, City Center"
    parking_capacity: int = 150
    working_hours_weekday: str = "06:00-23:00"
    working_hours_weekend: str = "08:00-22:00"
    price_per_hour: float = 5.00
    price_per_day: float = 40.00

    # API Configuration
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=True)
    cors_origins: List[str] = Field(default=["*"])

    session_ttl_seconds: int = Field(default=3600, description="Session TTL in seconds (default: 1 hour)")
    max_sessions: int = Field(default=1000, description="Maximum concurrent sessions")

    reservation_ttl_seconds: int = Field(default=3600, description="Reservation approval TTL in seconds (default: 1 hour)")
    max_reservations: int = Field(default=10000, description="Maximum reservations storage")

    email_notifications_enabled: bool = Field(
        default=False,
        description="Enable email notifications to admin about new reservations"
    )
    admin_email: str = Field(
        default="",
        description="Admin email address to receive reservation notifications"
    )
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: str = Field(default="", description="SMTP username for authentication")
    smtp_password: str = Field(default="", description="SMTP password for authentication")
    smtp_use_tls: bool = Field(default=True, description="Use TLS for SMTP connection")
    email_from: str = Field(default="parking-bot@example.com", description="Sender email address")
    email_from_name: str = Field(default="Parking Reservation System", description="Sender name displayed in email")
    admin_dashboard_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for admin dashboard (used in email links)"
    )

    admin_api_key: str = Field(
        default="",
        description="API key for administrative endpoints (REQUIRED for production)"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    def validate_config(self) -> None:
        import logging
        logger = logging.getLogger(__name__)

        if not self.openai_api_key or self.openai_api_key == "your-openai-api-key-here":
            raise ValueError(
                "OPENAI_API_KEY haven't been set up yet."
            )

        if not self.admin_api_key:
            logger.warning(
                "   SECURITY WARNING: ADMIN_API_KEY is not set! \n"
                "   Admin endpoints are UNPROTECTED and accessible without authentication.\n"
                "   Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'\n"
                "   Then set ADMIN_API_KEY in your .env file."
            )
    
    @property
    def deeplake_path(self) -> str:
        # If cloud path is configured, use it
        if self.deeplake_dataset_path.startswith("hub://"):
            return self.deeplake_dataset_path
        # Otherwise use local path
        return str(DATA_DIR / "deeplake_storage")


settings = Settings()
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
(DATA_DIR / "raw").mkdir(exist_ok=True)


def get_settings() -> Settings:
    return settings
