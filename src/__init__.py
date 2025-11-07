"""
Data Processing Pipeline

A comprehensive pipeline for generating synthetic SFT training data from markdown documents.

The pipeline consists of three main scripts:
1. Script 1 (chunk_md): Chunk markdown files into overlapping segments
2. Script 2 (generate_verify): Generate synthetic examples and verify quality
3. Script 3 (pack_json): Pack verified items into sharded datasets

For more information, see the project documentation.
"""

__version__ = "0.1.0"
__author__ = "Data Processing Team"

# Package metadata
__all__ = [
    "__version__",
    "__author__",
]

