"""ID generation utilities."""

import uuid
from datetime import datetime
from typing import Optional


def generate_uuid() -> str:
    """
    Generate UUIDv4.
    
    Returns a random UUID (version 4) as a lowercase string with hyphens.
    
    Returns:
        UUID string (lowercase, with hyphens)
        
    Examples:
        >>> id1 = generate_uuid()
        >>> len(id1)
        36
        >>> id1.count('-')
        4
    """
    return str(uuid.uuid4())


def generate_run_id(timestamp: Optional[datetime] = None) -> str:
    """
    Generate timestamped run ID.
    
    Creates a unique identifier for a pipeline run based on timestamp.
    Format: run_YYYYMMDD_HHMMSS
    
    Args:
        timestamp: Optional timestamp (defaults to current UTC time)
        
    Returns:
        Run ID in format "run_YYYYMMDD_HHMMSS"
        
    Examples:
        >>> from datetime import datetime
        >>> ts = datetime(2025, 11, 7, 14, 30, 45)
        >>> generate_run_id(ts)
        'run_20251107_143045'
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    return timestamp.strftime("run_%Y%m%d_%H%M%S")


def is_valid_uuid(value: str) -> bool:
    """
    Check if a string is a valid UUIDv4.
    
    Args:
        value: String to validate
        
    Returns:
        True if valid UUIDv4, False otherwise
        
    Examples:
        >>> is_valid_uuid("550e8400-e29b-41d4-a716-446655440000")
        True
        >>> is_valid_uuid("not-a-uuid")
        False
    """
    try:
        uuid_obj = uuid.UUID(value, version=4)
        return str(uuid_obj) == value
    except (ValueError, AttributeError):
        return False


def is_valid_run_id(value: str) -> bool:
    """
    Check if a string is a valid run ID.
    
    Args:
        value: String to validate
        
    Returns:
        True if valid run ID format, False otherwise
        
    Examples:
        >>> is_valid_run_id("run_20251107_143045")
        True
        >>> is_valid_run_id("invalid")
        False
    """
    if not value.startswith("run_"):
        return False
    
    parts = value.split("_")
    if len(parts) != 3:
        return False
    
    date_part = parts[1]
    time_part = parts[2]
    
    # Check format: YYYYMMDD and HHMMSS
    if len(date_part) != 8 or not date_part.isdigit():
        return False
    if len(time_part) != 6 or not time_part.isdigit():
        return False
    
    return True

