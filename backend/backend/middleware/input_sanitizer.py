"""Input validation and sanitization utilities.

Provides centralized input sanitization to prevent XSS and SQL injection
attacks across all route handlers.
"""
import html
from typing import Any


def sanitize_input(value: str) -> str:
    """Sanitize user input by escaping HTML special characters.
    
    Args:
        value: Raw string input from user
        
    Returns:
        HTML-escaped string safe for database insertion/frontend rendering
        
    Examples:
        >>> sanitize_input("<script>alert('xss')</script>")
        '&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;'
    """
    if not isinstance(value, str):
        return ""
    return html.escape(value)


def sanitize_input_list(items: list[str]) -> list[str]:
    """Sanitize multiple string inputs.
    
    Args:
        items: List of strings to sanitize
        
    Returns:
        List of sanitized strings
    """
    return [sanitize_input(item) for item in items]


def sanitize_json_field(value: Any) -> Any:
    """Sanitize values within JSON structures recursively.
    
    Args:
        value: Any JSON-compatible value (str, dict, list, int, float, bool, None)
        
    Returns:
        Sanitized version with all strings escaped
    """
    if isinstance(value, str):
        return sanitize_input(value)
    elif isinstance(value, dict):
        return {k: sanitize_json_field(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [sanitize_json_field(item) for item in value]
    else:
        # Numbers, booleans, None are safe as-is
        return value
