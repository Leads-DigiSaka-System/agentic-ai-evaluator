"""
Simple Clean Logging Setup with coloredlogs

This replaces emoji-heavy logging with clean, colored logging using coloredlogs library.
"""

import logging
import coloredlogs
from typing import Optional

def setup_clean_logging(level: str = "INFO", format_string: Optional[str] = None):
    """
    Setup clean logging with coloredlogs
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string (optional)
    """
    
    # Default clean format (no emojis, professional)
    if format_string is None:
        format_string = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        datefmt="%H:%M:%S"
    )
    
    # Install coloredlogs
    coloredlogs.install(
        level=level.upper(),
        fmt=format_string,
        datefmt="%H:%M:%S",
        field_styles={
            'asctime': {'color': 'green'},
            'hostname': {'color': 'magenta'},
            'levelname': {'color': 'cyan', 'bold': True},
            'name': {'color': 'blue'},
            'programname': {'color': 'cyan'},
            'username': {'color': 'yellow'}
        },
        level_styles={
            'debug': {'color': 'white'},
            'info': {'color': 'green'},
            'warning': {'color': 'yellow'},
            'error': {'color': 'red'},
            'critical': {'color': 'red', 'bold': True}
        }
    )

def get_clean_logger(name: str) -> logging.Logger:
    """
    Get a clean logger instance
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Example usage and migration guide
def example_usage():
    """Show how to use the clean logging"""
    
    # Setup (call this once at startup)
    setup_clean_logging("INFO")
    
    # Get logger
    logger = get_clean_logger(__name__)
    
    print("🎯 CLEAN LOGGING EXAMPLES:")
    print("=" * 40)
    
    # Instead of emoji prints, use clean logging
    logger.info("Starting file processing")
    logger.info("Extracted 2 reports from PDF")
    logger.warning("Some data missing, using defaults")
    logger.error("Failed to process file: invalid format")
    logger.debug("Debug information (only shown if DEBUG level)")
    
    print("\n📋 MIGRATION GUIDE:")
    print("=" * 20)
    print("OLD (emoji):")
    print('print("📊 Generating graph suggestions...")')
    print('print("✅ Generated 3 charts")')
    print('print("❌ Graph generation failed")')
    
    print("\nNEW (clean):")
    print('logger.info("Generating graph suggestions")')
    print('logger.info("Generated 3 charts")')
    print('logger.error("Graph generation failed")')


if __name__ == "__main__":
    example_usage()
