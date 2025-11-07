"""JSON schema validation utilities."""

import json
from pathlib import Path
from typing import Optional
import jsonschema
from jsonschema import Draft7Validator
import logging

logger = logging.getLogger(__name__)

# Schema cache
_schema_cache: dict[str, dict] = {}


def load_schema(schema_path: str) -> dict:
    """
    Load and cache JSON schema.
    
    Schemas are cached globally to avoid repeated file I/O.
    
    Args:
        schema_path: Path to schema file (relative to project root)
        
    Returns:
        Schema dictionary
        
    Raises:
        FileNotFoundError: If schema file doesn't exist
        json.JSONDecodeError: If schema file is invalid JSON
        
    Examples:
        >>> schema = load_schema("schemas/chunk.schema.json")
        >>> "properties" in schema
        True
    """
    if schema_path in _schema_cache:
        logger.debug(f"Using cached schema: {schema_path}")
        return _schema_cache[schema_path]
    
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        schema = json.load(f)
    
    _schema_cache[schema_path] = schema
    logger.debug(f"Loaded schema: {schema_path}")
    return schema


def validate_against_schema(
    data: dict,
    schema_path: str
) -> tuple[bool, list[str]]:
    """
    Validate data against JSON schema.
    
    Args:
        data: Data to validate
        schema_path: Path to schema file
        
    Returns:
        Tuple of (is_valid, error_messages)
        - is_valid: True if validation passed, False otherwise
        - error_messages: List of error messages (empty if valid)
        
    Examples:
        >>> data = {"chunk_id": "sha256:abc...", ...}
        >>> is_valid, errors = validate_against_schema(data, "schemas/chunk.schema.json")
        >>> is_valid
        True
    """
    try:
        schema = load_schema(schema_path)
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return True, []
        
        # Format error messages
        error_messages = []
        for e in errors:
            # Build path to the error location
            path = ".".join(str(p) for p in e.path) if e.path else "root"
            error_messages.append(f"{path}: {e.message}")
        
        return False, error_messages
    
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False, [f"Validation exception: {str(e)}"]


def validate_chunk(chunk: dict) -> tuple[bool, list[str]]:
    """
    Validate chunk against chunk schema.
    
    Args:
        chunk: Chunk data to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    return validate_against_schema(chunk, "schemas/chunk.schema.json")


def validate_generated_item(item: dict) -> tuple[bool, list[str]]:
    """
    Validate generated item against schema.
    
    Args:
        item: Generated item data to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    return validate_against_schema(item, "schemas/generated_item.schema.json")


def validate_verifier_report(report: dict) -> tuple[bool, list[str]]:
    """
    Validate verifier report against schema.
    
    Args:
        report: Verifier report data to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    return validate_against_schema(report, "schemas/verify_report.schema.json")


def validate_shard_manifest(manifest: dict) -> tuple[bool, list[str]]:
    """
    Validate shard manifest against schema.
    
    Args:
        manifest: Shard manifest data to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    return validate_against_schema(manifest, "schemas/shard_manifest.schema.json")


def clear_schema_cache() -> None:
    """Clear the global schema cache."""
    global _schema_cache
    _schema_cache.clear()
    logger.debug("Cleared schema cache")


def validate_file(file_path: str, schema_path: str) -> tuple[int, int, list[str]]:
    """
    Validate all records in a JSONL file against a schema.
    
    Args:
        file_path: Path to JSONL file
        schema_path: Path to schema file
        
    Returns:
        Tuple of (valid_count, invalid_count, error_messages)
        
    Examples:
        >>> valid, invalid, errors = validate_file("data.jsonl", "schemas/chunk.schema.json")
        >>> print(f"Valid: {valid}, Invalid: {invalid}")
    """
    valid_count = 0
    invalid_count = 0
    all_errors = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                is_valid, errors = validate_against_schema(data, schema_path)
                
                if is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1
                    all_errors.append(f"Line {line_num}: {'; '.join(errors)}")
            
            except json.JSONDecodeError as e:
                invalid_count += 1
                all_errors.append(f"Line {line_num}: Invalid JSON - {e}")
    
    return valid_count, invalid_count, all_errors

