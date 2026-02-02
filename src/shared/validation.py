"""
Shared input validation and sanitization for security.
Use for request body strings (e.g. chat message, search query) and optional ID/header length checks.
"""
import logging
from typing import Optional

from src.core.errors import ValidationError

logger = logging.getLogger(__name__)

# Max lengths for path/header/body IDs (optional hardening)
MAX_ID_LENGTH = 200
MAX_SESSION_ID_LENGTH = 200


def sanitize_string(
    value: str,
    max_length: Optional[int] = None,
    min_length: int = 0,
    remove_control_chars: bool = True,
    trim_whitespace: bool = True,
) -> str:
    """
    Sanitize a string: trim, remove control chars, enforce min/max length.
    Raises ValidationError if type is wrong or length constraints are violated.
    """
    if not isinstance(value, str):
        raise ValidationError(f"Expected string, got {type(value).__name__}")
    if remove_control_chars:
        allowed = {9, 10, 13, 32}
        value = "".join(c for c in value if ord(c) >= 32 or ord(c) in allowed)
    if trim_whitespace:
        value = value.strip()
    if len(value) < min_length:
        raise ValidationError(f"Input must be at least {min_length} characters")
    if max_length is not None and len(value) > max_length:
        logger.warning("Input truncated from %d to %d characters", len(value), max_length)
        value = value[:max_length]
    return value


def validate_message(message: str, max_length: int = 5000, min_length: int = 0) -> str:
    """Validate chat message: max 5000 chars, min 1 by default."""
    return sanitize_string(message, max_length=max_length, min_length=min_length)


def validate_search_query(query: str, max_length: int = 500, min_length: int = 0) -> str:
    """Validate search query: max 500 chars, min 1 by default."""
    return sanitize_string(query, max_length=max_length, min_length=min_length)


def validate_id(value: str, max_length: int = MAX_ID_LENGTH, name: str = "id") -> str:
    """
    Validate an ID string (path param, cache_id, form_id, etc.).
    Raises ValidationError if empty or too long.
    """
    if not isinstance(value, str):
        raise ValidationError(f"Expected string for {name}, got {type(value).__name__}")
    v = value.strip()
    if len(v) == 0:
        raise ValidationError(f"{name} cannot be empty")
    if len(v) > max_length:
        raise ValidationError(f"{name} must be at most {max_length} characters")
    return v


def validate_session_id(value: Optional[str], max_length: int = MAX_SESSION_ID_LENGTH) -> Optional[str]:
    """Validate optional session_id length. Returns None if value is None/empty."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("session_id must be a string")
    v = value.strip()
    if len(v) == 0:
        return None
    if len(v) > max_length:
        raise ValidationError(f"session_id must be at most {max_length} characters")
    return v


def validate_header_value(value: str, header_name: str, max_length: int = MAX_ID_LENGTH) -> str:
    """Validate header value (e.g. X-Cooperative, X-User-ID). Raises ValidationError if too long."""
    if not isinstance(value, str):
        raise ValidationError(f"{header_name} must be a string")
    v = value.strip()
    if len(v) == 0:
        raise ValidationError(f"{header_name} cannot be empty")
    if len(v) > max_length:
        raise ValidationError(f"{header_name} must be at most {max_length} characters")
    return v
