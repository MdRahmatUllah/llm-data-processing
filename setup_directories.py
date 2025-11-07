#!/usr/bin/env python3
"""
Setup script to create the complete directory structure for the data processing pipeline.

This script creates all necessary directories for:
- Configuration files and prompts
- JSON schemas
- Source code
- Input data
- Workspace (chunks, generations, verified, rejected, logs, cache)
- Output (shards)
- Tests and fixtures
"""

from pathlib import Path
import sys


# Directory structure to create
DIRS = [
    # Configuration
    "config",
    "config/prompts",
    
    # Schemas
    "schemas",
    
    # Source code
    "src",
    "src/common",
    
    # Input data
    "input",
    
    # Workspace directories
    "workspace",
    "workspace/chunks",
    "workspace/generations",
    "workspace/verified",
    "workspace/rejected",
    "workspace/logs",
    "workspace/cache",
    
    # Output directories
    "output",
    "output/shards",
    
    # Tests
    "tests",
    "tests/fixtures",
]


def setup_directories(verbose: bool = True) -> None:
    """
    Create all required directories for the pipeline.
    
    Args:
        verbose: If True, print status messages for each directory
    """
    created_count = 0
    existing_count = 0
    
    for dir_path in DIRS:
        path = Path(dir_path)
        
        if path.exists():
            if verbose:
                print(f"  ✓ {dir_path} (already exists)")
            existing_count += 1
        else:
            path.mkdir(parents=True, exist_ok=True)
            if verbose:
                print(f"  ✓ Created {dir_path}")
            created_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Directory setup complete!")
    print(f"  Created: {created_count} directories")
    print(f"  Already existed: {existing_count} directories")
    print(f"  Total: {len(DIRS)} directories")
    print(f"{'='*60}\n")


def verify_structure() -> bool:
    """
    Verify that all required directories exist.
    
    Returns:
        True if all directories exist, False otherwise
    """
    missing = []
    
    for dir_path in DIRS:
        if not Path(dir_path).exists():
            missing.append(dir_path)
    
    if missing:
        print("ERROR: Missing directories:")
        for path in missing:
            print(f"  - {path}")
        return False
    
    return True


def main():
    """Main entry point."""
    print("\n" + "="*60)
    print("Data Processing Pipeline - Directory Setup")
    print("="*60 + "\n")
    
    # Create directories
    setup_directories(verbose=True)
    
    # Verify structure
    if verify_structure():
        print("✓ All directories verified successfully!\n")
        return 0
    else:
        print("✗ Directory verification failed!\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

