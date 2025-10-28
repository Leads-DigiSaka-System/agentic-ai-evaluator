import logging
import re

class SafeLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    # Patterns to detect and hide sensitive info
    SENSITIVE_PATTERNS = [
        (r'/home/[^/]+', '/home/USER'),  # Hide username
        (r'C:\\Users\\[^\\]+', r'C:/Users/USER'),  # ← Changed to / instead of \ to avoid \U issue
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'EMAIL_HIDDEN'),
        (r'\d{3}-\d{2}-\d{4}', 'XXX-XX-XXXX'),  # Hide SSN
        (r'\+\d{10,}', 'PHONE_HIDDEN'),
    ]
    
    def sanitize(self, message: str) -> str:
        """Remove sensitive info before logging"""
        sanitized = message
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized)
        
        # Truncate very long messages (avoid logging full file content)
        if len(sanitized) > 200:
            sanitized = sanitized[:200] + "... (truncated)"
        
        return sanitized
    
    def info(self, message: str, **kwargs):
        self.logger.info(self.sanitize(str(message)), **kwargs)
    
    def error(self, message: str, **kwargs):
        self.logger.error(self.sanitize(str(message)), **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(self.sanitize(str(message)), **kwargs)
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(self.sanitize(str(message)), **kwargs)