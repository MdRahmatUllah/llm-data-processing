"""JSON parsing utilities with robust error handling and sanitization."""

import json
import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def sanitize_json_string(json_str: str) -> str:
    r"""
    Sanitize a JSON string by fixing common escape sequence issues.

    This function handles:
    - Invalid escape sequences (e.g., \b, \f, \x)
    - Unescaped backslashes in paths (e.g., C:\Users -> C:\\Users)
    - Preserves valid escape sequences (\n, \t, \", \\, \/, \r, \uXXXX)

    Args:
        json_str: Raw JSON string that may contain invalid escape sequences

    Returns:
        Sanitized JSON string with properly escaped backslashes

    Examples:
        >>> sanitize_json_string('{"path": "C:\\Users\\file"}')
        '{"path": "C:\\\\Users\\\\file"}'
    """
    # First, let's try to identify strings within the JSON
    # We'll process the content between quotes more carefully
    
    result = []
    i = 0
    in_string = False
    escape_next = False
    
    while i < len(json_str):
        char = json_str[i]
        
        # Toggle string state when we encounter unescaped quotes
        if char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
            i += 1
            escape_next = False
            continue
        
        # Handle escape sequences inside strings
        if in_string and char == '\\' and not escape_next:
            # Look ahead to see what's being escaped
            if i + 1 < len(json_str):
                next_char = json_str[i + 1]
                
                # Valid JSON escape sequences: " \ / b f n r t u
                if next_char in ['"', '\\', '/', 'b', 'f', 'n', 'r', 't']:
                    # Valid escape sequence - keep as is
                    result.append(char)
                    escape_next = True
                elif next_char == 'u':
                    # Unicode escape - validate it has 4 hex digits
                    if i + 5 < len(json_str) and all(c in '0123456789abcdefABCDEF' for c in json_str[i+2:i+6]):
                        # Valid unicode escape
                        result.append(char)
                        escape_next = True
                    else:
                        # Invalid unicode escape - escape the backslash
                        result.append('\\\\')
                        escape_next = False
                else:
                    # Invalid escape sequence - escape the backslash
                    result.append('\\\\')
                    escape_next = False
            else:
                # Backslash at end of string - escape it
                result.append('\\\\')
                escape_next = False
        else:
            result.append(char)
            escape_next = False
        
        i += 1
    
    return ''.join(result)


def extract_json_from_markdown(content: str) -> str:
    """
    Extract JSON content from markdown code fences.
    
    Handles:
    - ```json ... ```
    - ``` ... ```
    - Plain JSON without fences
    
    Args:
        content: Raw content that may contain markdown fences
        
    Returns:
        Extracted JSON string
    """
    content = content.strip()
    
    # Try to extract from ```json fence
    if '```json' in content:
        parts = content.split('```json', 1)
        if len(parts) > 1:
            json_part = parts[1].split('```', 1)[0]
            return json_part.strip()
    
    # Try to extract from ``` fence
    if '```' in content:
        parts = content.split('```', 1)
        if len(parts) > 1:
            json_part = parts[1].split('```', 1)[0]
            return json_part.strip()
    
    # No fences found - return as is
    return content


def parse_json_robust(
    json_str: str,
    sanitize: bool = True,
    extract_markdown: bool = True
) -> Any:
    """
    Parse JSON with robust error handling and automatic sanitization.
    
    This function attempts multiple strategies to parse JSON:
    1. Direct parsing (if already valid)
    2. Extract from markdown fences
    3. Sanitize escape sequences and retry
    4. Remove trailing commas and retry
    
    Args:
        json_str: JSON string to parse
        sanitize: Whether to attempt sanitization on parse errors
        extract_markdown: Whether to extract from markdown fences
        
    Returns:
        Parsed JSON object (dict, list, etc.)
        
    Raises:
        json.JSONDecodeError: If all parsing attempts fail
        
    Examples:
        >>> parse_json_robust('```json\\n{"key": "value"}\\n```')
        {'key': 'value'}
    """
    original_str = json_str
    
    # Step 1: Extract from markdown if needed
    if extract_markdown:
        json_str = extract_json_from_markdown(json_str)
    
    # Step 2: Try direct parsing first
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.debug(f"Initial JSON parse failed: {e}")
    
    # Step 3: Try sanitizing escape sequences
    if sanitize:
        try:
            sanitized = sanitize_json_string(json_str)
            logger.debug("Attempting parse with sanitized JSON")
            return json.loads(sanitized)
        except json.JSONDecodeError as e:
            logger.debug(f"Sanitized JSON parse failed: {e}")
    
    # Step 4: Try removing trailing commas (common LLM mistake)
    try:
        # Remove trailing commas before } or ]
        cleaned = re.sub(r',(\s*[}\]])', r'\1', json_str)
        logger.debug("Attempting parse with trailing commas removed")
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.debug(f"Cleaned JSON parse failed: {e}")
    
    # Step 5: Try both sanitization and comma removal
    if sanitize:
        try:
            sanitized = sanitize_json_string(json_str)
            cleaned = re.sub(r',(\s*[}\]])', r'\1', sanitized)
            logger.debug("Attempting parse with sanitization + comma removal")
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.debug(f"Final parse attempt failed: {e}")
    
    # All attempts failed - raise the original error with helpful context
    logger.error("All JSON parsing attempts failed")
    logger.error(f"Original content (first 500 chars): {original_str[:500]}")
    logger.error(f"Extracted JSON (first 500 chars): {json_str[:500]}")
    
    # Try one more time to get a better error message
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Failed to parse JSON after all attempts. {e.msg}",
            e.doc,
            e.pos
        )


def save_failed_json(
    content: str,
    error: Exception,
    output_path: str,
    context: Optional[dict] = None
) -> None:
    """
    Save failed JSON parsing attempts for debugging.
    
    Args:
        content: The content that failed to parse
        error: The exception that was raised
        output_path: Path to save the debug file
        context: Optional context information (chunk_id, etc.)
    """
    from pathlib import Path
    from datetime import datetime
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write(f"JSON Parsing Error Debug Report\n")
        f.write(f"Timestamp: {datetime.utcnow().isoformat()}Z\n")
        f.write("=" * 80 + "\n\n")
        
        if context:
            f.write("Context:\n")
            for key, value in context.items():
                f.write(f"  {key}: {value}\n")
            f.write("\n")
        
        f.write(f"Error: {type(error).__name__}: {error}\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("Raw Content:\n")
        f.write("=" * 80 + "\n")
        f.write(content)
        f.write("\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("Extracted JSON:\n")
        f.write("=" * 80 + "\n")
        f.write(extract_json_from_markdown(content))
        f.write("\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("Sanitized JSON:\n")
        f.write("=" * 80 + "\n")
        f.write(sanitize_json_string(extract_json_from_markdown(content)))
        f.write("\n")
    
    logger.info(f"Saved failed JSON debug info to: {output_path}")


def validate_json_string(json_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate a JSON string without parsing it.
    
    Args:
        json_str: JSON string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if valid JSON, False otherwise
        - error_message: Error message if invalid, None if valid
    """
    try:
        json.loads(json_str)
        return True, None
    except json.JSONDecodeError as e:
        return False, f"{e.msg} at line {e.lineno} column {e.colno}"
    except Exception as e:
        return False, str(e)

