"""
Common utilities for the data processing pipeline.

This package contains shared modules used across all scripts:
- hashing: SHA256/SHA1 hashing for chunk IDs and file integrity
- ids: UUID and run ID generation
- tokenizers: Tokenization support (tiktoken, SentencePiece)
- validation: JSON schema validation
- io_utils: File I/O, JSONL handling, rate limiting
- config: Configuration file loading and management
- model_client: API client for model interactions
- prompt_utils: Jinja2 template rendering for prompts
"""

__all__ = [
    "hashing",
    "ids",
    "tokenizers",
    "validation",
    "io_utils",
    "config",
    "model_client",
    "prompt_utils",
]

