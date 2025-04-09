"""
Authentication dependencies for API access control.

This module provides FastAPI dependencies to authenticate requests
using bearer tokens and verify admin access.
"""

from fastapi import Request, HTTPException, Depends, status
from typing import Dict, Any
import logging

# Import settings from the correct location
from src.config.settings import settings

logger = logging.getLogger(__name__)

AUTH_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing authentication token",
    headers={"WWW-Authenticate": "Bearer"},
)

ADMIN_FORBIDDEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Admin access required",
)

async def get_current_identifier(request: Request) -> str:
    """
    Dependency to extract token, validate it against ACCESS_TOKENS_DICT,
    and return the associated identifier.
    Raises HTTPException 401 if invalid/missing.
    """
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ")[1]

    if not token:
        logger.warning("Missing or malformed Authorization header.")
        raise AUTH_EXCEPTION

    # Access the parsed dictionary from settings
    token_map: Dict[str, str] = settings.get('ACCESS_TOKENS_DICT', {})

    for identifier, valid_token in token_map.items():
        # IMPORTANT: Use a secure comparison (though basic equality is shown here)
        # In production, consider timing-attack resistant comparison if critical
        if token == valid_token:
            logger.info(f"Authenticated request with identifier: {identifier}")
            return identifier # Return the identifier (key)

    logger.warning(f"Invalid token received: {token[:5]}...") # Log sanitized token
    raise AUTH_EXCEPTION

async def verify_admin_token(request: Request) -> bool:
    """
    Dependency to verify if the provided token matches the ADMIN_TOKEN.
    Raises HTTPException 403 if invalid/missing.
    """
    admin_token = settings.get('ADMIN_TOKEN')
    if not admin_token:
        logger.error("Admin endpoint accessed but ADMIN_TOKEN is not configured.")
        raise ADMIN_FORBIDDEN_EXCEPTION # Or 500 Internal Server Error

    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ")[1]

    if not token:
        logger.warning("Admin endpoint access attempt without token.")
        raise ADMIN_FORBIDDEN_EXCEPTION

    # IMPORTANT: Use secure comparison
    if token == admin_token:
        logger.info("Admin access granted.")
        return True
    else:
        logger.warning("Invalid admin token received.")
        raise ADMIN_FORBIDDEN_EXCEPTION 