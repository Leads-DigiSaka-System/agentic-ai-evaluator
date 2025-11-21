"""
Season detection utility for agricultural reports.

Determines wet/dry season based on planting_date only.
Uses Philippines season calendar:
- Wet Season: June to November (rainy months)
- Dry Season: December to May (dry months)
"""

from datetime import datetime
from typing import Optional, Literal


def detect_season(date_str: Optional[str]) -> Optional[Literal["wet", "dry"]]:
    """
    Detect season (wet/dry) based on date.
    
    Philippines Season Calendar:
    - Wet Season: June (6) to November (11) - rainy months
    - Dry Season: December (12) to May (5) - dry months
    
    Args:
        date_str: Date string in ISO format (YYYY-MM-DD) or any parseable format
        
    Returns:
        "wet", "dry", or None if date cannot be parsed
        
    Examples:
        >>> detect_season("2024-06-15")  # June - Wet season
        'wet'
        >>> detect_season("2024-01-15")  # January - Dry season
        'dry'
        >>> detect_season("2024-12-01")  # December - Dry season
        'dry'
    """
    if not date_str:
        return None
    
    try:
        # Try parsing ISO format first (YYYY-MM-DD)
        if isinstance(date_str, str):
            # Handle various date formats
            date_str = date_str.strip()
            
            # If it's ISO format with time, extract date part
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            
            # Parse the date
            try:
                # Try ISO format first
                date_obj = datetime.fromisoformat(date_str)
            except ValueError:
                # Try other common formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']:
                    try:
                        date_obj = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # If all formats fail, return None
                    return None
        else:
            # If it's already a datetime object
            date_obj = date_str if isinstance(date_str, datetime) else None
            if date_obj is None:
                return None
        
        # Get month (1-12)
        month = date_obj.month
        
        # Determine season based on Philippines calendar
        # Wet: June (6) to November (11)
        # Dry: December (12) to May (5)
        if 6 <= month <= 11:
            return "wet"
        else:
            return "dry"
            
    except Exception:
        # If parsing fails, return None
        return None


def detect_season_from_dates(
    application_date: Optional[str] = None,
    planting_date: Optional[str] = None
) -> Optional[Literal["wet", "dry"]]:
    """
    Detect season from planting_date only.
    Uses only planting_date to determine the season.
    
    Args:
        application_date: Date of application (not used, kept for compatibility)
        planting_date: Date of planting (used to determine season)
        
    Returns:
        "wet", "dry", or None if planting_date cannot be parsed
        
    Examples:
        >>> detect_season_from_dates("2024-07-15", "2024-06-01")
        'wet'  # Uses planting_date (June)
        >>> detect_season_from_dates(None, "2024-01-15")
        'dry'  # Uses planting_date (January)
    """
   
    date_to_use = planting_date
    
    if not date_to_use:
        return None
    
    return detect_season(date_to_use)


def get_season_name(season: Optional[Literal["wet", "dry"]]) -> str:
    """
    Get human-readable season name.
    
    Args:
        season: "wet" or "dry"
        
    Returns:
        "Wet Season", "Dry Season", or "Unknown"
    """
    if season == "wet":
        return "Wet Season"
    elif season == "dry":
        return "Dry Season"
    else:
        return "Unknown"


def get_season_months(season: Optional[Literal["wet", "dry"]]) -> list[str]:
    """
    Get list of months for the season.
    
    Args:
        season: "wet" or "dry"
        
    Returns:
        List of month names
    """
    if season == "wet":
        return ["June", "July", "August", "September", "October", "November"]
    elif season == "dry":
        return ["December", "January", "February", "March", "April", "May"]
    else:
        return []

