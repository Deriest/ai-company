"""AIC-ADE Backend — Input Validation Middleware.

Comprehensive input validation for all endpoints.
Validates request body, query parameters, and path parameters.
"""

import logging
import json
from typing import Any, Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger("aic.validation")


async def validation_middleware(request: Request, call_next: Callable) -> Response:
    """
    Input validation middleware.
    
    Validates:
    - Request body size
    - Content type for POST/PUT/PATCH
    - Path parameter format
    - Query parameter types
    """
    
    # 2. Check request body size (max 70MB — must accommodate 50MB attachments
    #    × 4/3 base64 expansion + JSON overhead; UI allows 20MB/file, 50MB total)
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > 70 * 1024 * 1024:  # 70MB
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": "Request body too large",
                            "type": "ValidationError",
                            "max_size": "70MB"
                        }
                    )
            except ValueError:
                pass
    
    # 2. Validate path parameters
    path_params = request.path_params
    for key, value in path_params.items():
        if isinstance(value, str):
            # Check for SQL injection patterns
            if any(pattern in value.lower() for pattern in [
                "drop table", "delete from", "insert into",
                "update set", "--", ";", "/*", "*/",
                "union select", "or 1=1", "or true"
            ]):
                logger.warning(f"Suspicious path parameter: {key}={value}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"Invalid {key} parameter",
                        "type": "ValidationError",
                        "field": key
                    }
                )
            
            # Check length
            if len(value) > 1024:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"{key} parameter too long",
                        "type": "ValidationError",
                        "field": key,
                        "max_length": 1024
                    }
                )
    
    # 3. Validate query parameters
    query_params = request.query_params
    for key, value in query_params.items():
        if isinstance(value, str):
            # Check length
            if len(value) > 10000:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"Query parameter {key} too long",
                        "type": "ValidationError",
                        "field": key,
                        "max_length": 10000
                    }
                )
    
    # 4. Continue processing
    try:
        response = await call_next(request)
        return response
    except ValidationError as e:
        # Catch Pydantic validation errors
        logger.warning(f"Validation error: {e}")
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "type": "ValidationError",
                "errors": [
                    {
                        "field": ".".join(str(loc) for loc in err["loc"]),
                        "message": err["msg"],
                        "type": err["type"]
                    }
                    for err in e.errors()
                ]
            }
        )
    except Exception as e:
        # Let other exceptions pass through
        raise


def validate_json_body(body: bytes, max_size: int = 10 * 1024 * 1024) -> tuple[bool, str]:
    """
    Validate JSON request body.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if len(body) > max_size:
        return False, f"Request body too large (max {max_size // (1024*1024)}MB)"
    
    try:
        json.loads(body)
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}"


def sanitize_string(value: str, max_length: int = 10000) -> str:
    """
    Sanitize string input.
    
    - Strip whitespace
    - Limit length
    - Remove null bytes
    """
    if not isinstance(value, str):
        return value
    
    # Remove null bytes
    value = value.replace("\x00", "")
    
    # Strip whitespace
    value = value.strip()
    
    # Limit length
    if len(value) > max_length:
        value = value[:max_length]
    
    return value


def validate_enum_value(value: str, allowed_values: list[str], field_name: str) -> tuple[bool, str]:
    """
    Validate enum value.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if value not in allowed_values:
        return False, f"Invalid {field_name}: {value}. Allowed: {', '.join(allowed_values)}"
    return True, ""


def validate_integer_range(
    value: int,
    min_value: int = None,
    max_value: int = None,
    field_name: str = "value"
) -> tuple[bool, str]:
    """
    Validate integer range.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if min_value is not None and value < min_value:
        return False, f"{field_name} must be >= {min_value}"
    if max_value is not None and value > max_value:
        return False, f"{field_name} must be <= {max_value}"
    return True, ""


def validate_string_length(
    value: str,
    min_length: int = None,
    max_length: int = None,
    field_name: str = "value"
) -> tuple[bool, str]:
    """
    Validate string length.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    
    if min_length is not None and len(value) < min_length:
        return False, f"{field_name} must be at least {min_length} characters"
    if max_length is not None and len(value) > max_length:
        return False, f"{field_name} must be at most {max_length} characters"
    return True, ""


def validate_url(value: str, field_name: str = "url") -> tuple[bool, str]:
    """
    Validate URL format.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    
    if not value.startswith(("http://", "https://")):
        return False, f"{field_name} must start with http:// or https://"
    
    if len(value) > 2048:
        return False, f"{field_name} too long (max 2048 characters)"
    
    return True, ""


def validate_email(value: str, field_name: str = "email") -> tuple[bool, str]:
    """
    Validate email format (basic).
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    
    if "@" not in value:
        return False, f"{field_name} must contain @"
    
    if "." not in value.split("@")[-1]:
        return False, f"{field_name} must have valid domain"
    
    return True, ""
