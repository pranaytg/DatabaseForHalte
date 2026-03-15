"""
LWA (Login with Amazon) Authentication Module

Handles OAuth2 token acquisition and caching for SP-API access.
The python-amazon-sp-api library handles LWA internally, but this module
provides explicit token management for:
- Manual API calls outside the library
- Token health checks
- Credential validation at startup

Token lifecycle:
  1. Use the Refresh Token + Client ID + Client Secret
  2. POST to https://api.amazon.com/auth/o2/token
  3. Receive a short-lived Access Token (valid ~1 hour)
  4. Cache it and reuse until expiry
"""

import time
import logging
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# ── Token cache ─────────────────────────────────────────────────────────────

_cached_token: Optional[str] = None
_token_expiry: float = 0.0  # Unix timestamp

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

# Refresh 5 minutes before actual expiry to avoid edge-case failures
EXPIRY_BUFFER_SECONDS = 300


def get_access_token() -> str:
    """
    Get a valid SP-API access token, fetching a new one if the cached token
    has expired or is about to expire.

    Returns:
        A valid LWA access token string.

    Raises:
        RuntimeError: If token acquisition fails.
    """
    global _cached_token, _token_expiry

    if _cached_token and time.time() < (_token_expiry - EXPIRY_BUFFER_SECONDS):
        logger.debug("Using cached LWA access token")
        return _cached_token

    logger.info("Requesting new LWA access token")
    _cached_token, _token_expiry = _request_new_token()
    return _cached_token


def _request_new_token() -> tuple[str, float]:
    """
    POST to Amazon's LWA endpoint to exchange the refresh token
    for a new access token.

    Returns:
        Tuple of (access_token, expiry_timestamp).
    """
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": settings.sp_api_refresh_token,
        "client_id": settings.sp_api_lwa_app_id,
        "client_secret": settings.sp_api_lwa_client_secret,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(LWA_TOKEN_URL, data=payload)

        if response.status_code != 200:
            error_body = response.text
            logger.error(f"LWA token request failed ({response.status_code}): {error_body}")
            raise RuntimeError(
                f"LWA authentication failed: {response.status_code} - {error_body}"
            )

        data = response.json()
        access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)  # Default 1 hour
        expiry_time = time.time() + expires_in

        logger.info(f"LWA access token acquired (expires in {expires_in}s)")
        return access_token, expiry_time

    except httpx.RequestError as e:
        logger.error(f"Network error during LWA token request: {e}")
        raise RuntimeError(f"LWA network error: {e}")


def validate_credentials() -> dict:
    """
    Validate that SP-API credentials are configured and working.
    Called at startup to fail fast if auth is broken.

    Returns:
        Status dict with credential health info.
    """
    result = {
        "lwa_app_id_set": bool(settings.sp_api_lwa_app_id),
        "client_secret_set": bool(settings.sp_api_lwa_client_secret),
        "refresh_token_set": bool(settings.sp_api_refresh_token),
        "token_valid": False,
        "error": None,
    }

    if not all([result["lwa_app_id_set"], result["client_secret_set"], result["refresh_token_set"]]):
        result["error"] = "Missing SP-API credentials in .env"
        return result

    try:
        token = get_access_token()
        result["token_valid"] = bool(token)
    except Exception as e:
        result["error"] = str(e)

    return result


def clear_token_cache():
    """Force clear the cached token (useful for credential rotation)."""
    global _cached_token, _token_expiry
    _cached_token = None
    _token_expiry = 0.0
    logger.info("LWA token cache cleared")
