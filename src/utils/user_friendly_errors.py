"""
User-friendly error message utilities.

Converts technical error messages to user-friendly messages for display in the UI.
"""
from typing import Optional
import re

# Error pattern mappings for user-friendly messages
ERROR_PATTERNS = [
    # File-related errors
    {
        "pattern": re.compile(r"invalid file|file format|unsupported file|file type", re.IGNORECASE),
        "message": "The file format is not supported. Please upload a PDF, JPG, JPEG, or PNG file."
    },
    {
        "pattern": re.compile(r"file too large|file size|exceeds|maximum size", re.IGNORECASE),
        "message": "The file is too large. Please upload a file smaller than 50MB."
    },
    {
        "pattern": re.compile(r"file not found|file missing|no file|file empty", re.IGNORECASE),
        "message": "No file was uploaded. Please select a file and try again."
    },
    {
        "pattern": re.compile(r"corrupted|invalid pdf|damaged file", re.IGNORECASE),
        "message": "The file appears to be corrupted or damaged. Please try a different file."
    },
    
    # Processing errors
    {
        "pattern": re.compile(r"timeout|timed out|took too long", re.IGNORECASE),
        "message": "The processing took too long. Please try again with a smaller file or check your internet connection."
    },
    {
        "pattern": re.compile(r"processing failed|failed to process|error processing", re.IGNORECASE),
        "message": "We encountered an issue while processing your file. Please try again."
    },
    {
        "pattern": re.compile(r"extraction failed|failed to extract|could not extract", re.IGNORECASE),
        "message": "We couldn't extract content from your file. Please ensure the file contains readable text."
    },
    {
        "pattern": re.compile(r"analysis failed|failed to analyze|could not analyze", re.IGNORECASE),
        "message": "We couldn't analyze your file. Please check if the file contains valid data."
    },
    
    # Content validation errors
    {
        "pattern": re.compile(r"no text|empty content|no content|blank", re.IGNORECASE),
        "message": "The file appears to be empty or contains no readable text. Please upload a file with content."
    },
    {
        "pattern": re.compile(r"invalid content|content validation|validation failed", re.IGNORECASE),
        "message": "The file content couldn't be validated. Please ensure the file contains valid agricultural data."
    },
    {
        "pattern": re.compile(r"insufficient data|not enough data|data missing", re.IGNORECASE),
        "message": "The file doesn't contain enough data for analysis. Please upload a complete file."
    },
    
    # Network/API errors
    {
        "pattern": re.compile(r"network|connection|fetch|request failed", re.IGNORECASE),
        "message": "Connection error. Please check your internet connection and try again."
    },
    {
        "pattern": re.compile(r"server error|500|internal error|service unavailable", re.IGNORECASE),
        "message": "Our servers are experiencing issues. Please try again in a few moments."
    },
    {
        "pattern": re.compile(r"not found|404|job not found|expired", re.IGNORECASE),
        "message": "The processing job was not found or has expired. Please start a new analysis."
    },
    
    # JSON/parsing errors (should be generic for users)
    {
        "pattern": re.compile(r"json|parse|invalid json|syntax error|escape", re.IGNORECASE),
        "message": "There was an issue processing the response. Please try again."
    },
    
    # Langfuse/monitoring errors (should not be shown to users)
    {
        "pattern": re.compile(r"langfuse|trace|monitoring|observability|get_trace_id", re.IGNORECASE),
        "message": "Processing completed, but there was an issue with logging. Your results should still be available."
    },
]


def get_user_friendly_error(error: Optional[str]) -> str:
    """
    Convert a technical error message to a user-friendly message.
    
    Args:
        error: Technical error message
        
    Returns:
        User-friendly error message
    """
    if not error:
        return "An error occurred. Please try again."
    
    error_str = str(error)
    
    # Check if error message is already user-friendly (short and simple)
    if len(error_str) < 100 and not any(keyword in error_str.lower() for keyword in ["exception", "error:", "traceback", "file", "line"]):
        # Check if it matches any technical pattern
        is_technical = any(pattern["pattern"].search(error_str) for pattern in ERROR_PATTERNS)
        if not is_technical:
            # Likely already user-friendly
            return error_str
    
    # Try to match error patterns
    for error_pattern in ERROR_PATTERNS:
        if error_pattern["pattern"].search(error_str):
            return error_pattern["message"]
    
    # If no pattern matches, return a generic friendly message
    if len(error_str) > 200:
        # Very long error messages are likely technical
        return "We encountered an issue processing your file. Please try again or contact support if the problem persists."
    
    # For shorter errors, try to clean them up
    cleaned = error_str
    # Remove common technical prefixes
    cleaned = re.sub(r"^(Error|Exception|Traceback):\s*", "", cleaned, flags=re.IGNORECASE)
    # Remove file paths and line numbers
    cleaned = re.sub(r"File\s+['\"].*?['\"].*?line\s+\d+", "", cleaned)
    # Remove traceback info
    cleaned = re.sub(r"Traceback.*?$", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    
    # If cleaned message is still technical, use generic
    if ":" in cleaned and len(cleaned.split(":")) > 2:
        return "We encountered an issue processing your file. Please try again."
    
    # Return cleaned message if it's reasonable
    return cleaned if cleaned else "An error occurred. Please try again."


def get_user_friendly_error_title(error: Optional[str]) -> str:
    """
    Get a user-friendly error title based on error type.
    
    Args:
        error: Technical error message
        
    Returns:
        User-friendly error title
    """
    if not error:
        return "Error"
    
    error_str = str(error).lower()
    
    if any(keyword in error_str for keyword in ["file", "upload", "format"]):
        return "File Upload Error"
    elif any(keyword in error_str for keyword in ["processing", "analysis", "extraction"]):
        return "Processing Error"
    elif any(keyword in error_str for keyword in ["network", "connection", "timeout"]):
        return "Connection Error"
    elif any(keyword in error_str for keyword in ["not found", "404", "expired"]):
        return "Not Found"
    elif any(keyword in error_str for keyword in ["unauthorized", "permission", "401", "403"]):
        return "Authentication Error"
    else:
        return "Error"

