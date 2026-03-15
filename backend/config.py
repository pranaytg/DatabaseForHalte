"""
Application settings — loaded from .env via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── Supabase ──
    supabase_url: str
    supabase_key: str  # service-role key
    database_url: str

    # ── Amazon SP-API ──
    sp_api_account_id: str = ""
    sp_api_marketplace_id: str = "A21TJRUUN4KGV"
    sp_api_lwa_app_id: str = ""
    sp_api_lwa_client_secret: str = ""
    sp_api_refresh_token: str = ""

    # ── App ──
    cors_origins: str = "http://localhost:3000"
    backend_url: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sp_api_credentials(self) -> dict:
        """Credentials dict expected by python-amazon-sp-api."""
        return {
            "lwa_app_id": self.sp_api_lwa_app_id,
            "lwa_client_secret": self.sp_api_lwa_client_secret,
            "refresh_token": self.sp_api_refresh_token,
        }

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
