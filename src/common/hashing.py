"""Hashing utilities for chunk IDs and file integrity."""

import hashlib
from typing import Union


def sha256_hash(data: str) -> str:
    """
    Compute SHA256 hash of string data.
    
    Args:
        data: String to hash
        
    Returns:
        Hash in format "sha256:hexdigest"
        
    Examples:
        >>> sha256_hash("hello world")
        'sha256:b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
    """
    h = hashlib.sha256(data.encode('utf-8')).hexdigest()
    return f"sha256:{h}"


def sha1_hash(data: bytes) -> str:
    """
    Compute SHA1 hash of binary data.
    
    Args:
        data: Bytes to hash
        
    Returns:
        Hex digest string (no prefix)
        
    Examples:
        >>> sha1_hash(b"hello world")
        '2aae6c35c94fcfb415dbe95f408b9ce91ee846ed'
    """
    return hashlib.sha1(data).hexdigest()


def compute_chunk_id(
    project: str,
    file_relpath: str,
    chunk_index: int,
    file_sha1: str
) -> str:
    """
    Generate deterministic chunk ID.
    
    The chunk ID is computed as SHA256 of a composite string containing:
    - Project name
    - File relative path
    - Chunk index
    - File SHA1 hash
    
    This ensures that:
    1. Chunk IDs are deterministic (same input = same ID)
    2. Chunk IDs are unique across projects and files
    3. Chunk IDs change if the source file changes
    
    Format: sha256(project|file_relpath|chunk_index|file_sha1)
    
    Args:
        project: Project name
        file_relpath: Relative path from project root
        chunk_index: Zero-based chunk index
        file_sha1: SHA1 hash of source file
        
    Returns:
        Chunk ID in format "sha256:hexdigest"
        
    Examples:
        >>> compute_chunk_id("MyProject", "docs/intro.md", 0, "abc123")
        'sha256:...'
    """
    composite = f"{project}|{file_relpath}|{chunk_index}|{file_sha1}"
    return sha256_hash(composite)


def compute_file_sha1(file_path: str) -> str:
    """
    Compute SHA1 hash of a file's contents.
    
    Reads the file in chunks to handle large files efficiently.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA1 hex digest string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    sha1 = hashlib.sha1()
    
    with open(file_path, 'rb') as f:
        # Read in 64KB chunks
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha1.update(chunk)
    
    return sha1.hexdigest()

