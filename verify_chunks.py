"""Verification script to validate chunked data before running Script 2."""

import json
import sys
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.common.validation import validate_chunk
from src.common.io_utils import find_files


def verify_chunks(workspace_path: Path):
    """
    Verify all chunk files in the workspace.
    
    Args:
        workspace_path: Path to workspace directory
    """
    print("=" * 80)
    print("Chunk Data Verification")
    print("=" * 80)
    print()
    
    chunks_dir = workspace_path / "chunks"
    
    if not chunks_dir.exists():
        print(f"❌ ERROR: Chunks directory not found: {chunks_dir}")
        return False
    
    print(f"📁 Chunks directory: {chunks_dir}")
    print()
    
    # Find all chunk files
    chunk_files = find_files(chunks_dir, "**/*.chunks.jsonl")
    
    if not chunk_files:
        print(f"❌ ERROR: No chunk files found in {chunks_dir}")
        return False
    
    print(f"✅ Found {len(chunk_files)} chunk files")
    print()
    
    # Statistics
    stats = {
        "total_files": len(chunk_files),
        "total_chunks": 0,
        "valid_chunks": 0,
        "invalid_chunks": 0,
        "projects": defaultdict(int),
        "files_by_project": defaultdict(list),
        "chunks_by_file": {},
        "errors": []
    }
    
    # Process each file
    print("-" * 80)
    print("Processing chunk files...")
    print("-" * 80)
    print()
    
    for chunk_file in sorted(chunk_files):
        rel_path = chunk_file.relative_to(chunks_dir)
        print(f"📄 {rel_path}")
        
        try:
            # Read file
            with open(chunk_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            file_chunks = 0
            file_valid = 0
            file_invalid = 0
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # Parse JSON
                    chunk = json.loads(line)
                    stats["total_chunks"] += 1
                    file_chunks += 1
                    
                    # Validate chunk
                    is_valid, errors = validate_chunk(chunk)
                    
                    if is_valid:
                        stats["valid_chunks"] += 1
                        file_valid += 1
                        
                        # Track project
                        project = chunk.get("project", "unknown")
                        stats["projects"][project] += 1
                        if chunk_file.name not in stats["files_by_project"][project]:
                            stats["files_by_project"][project].append(chunk_file.name)
                    else:
                        stats["invalid_chunks"] += 1
                        file_invalid += 1
                        error_msg = f"  Line {line_num}: Validation failed: {errors}"
                        stats["errors"].append(error_msg)
                        print(f"  ❌ {error_msg}")
                
                except json.JSONDecodeError as e:
                    stats["invalid_chunks"] += 1
                    file_invalid += 1
                    error_msg = f"  Line {line_num}: JSON parse error: {e}"
                    stats["errors"].append(error_msg)
                    print(f"  ❌ {error_msg}")
            
            stats["chunks_by_file"][str(rel_path)] = {
                "total": file_chunks,
                "valid": file_valid,
                "invalid": file_invalid
            }
            
            if file_invalid == 0:
                print(f"  ✅ {file_chunks} chunks (all valid)")
            else:
                print(f"  ⚠️  {file_chunks} chunks ({file_valid} valid, {file_invalid} invalid)")
            print()
        
        except Exception as e:
            error_msg = f"  Error reading file: {e}"
            stats["errors"].append(error_msg)
            print(f"  ❌ {error_msg}")
            print()
    
    # Print summary
    print("=" * 80)
    print("Verification Summary")
    print("=" * 80)
    print()
    
    print(f"📊 Statistics:")
    print(f"  • Total chunk files: {stats['total_files']}")
    print(f"  • Total chunks: {stats['total_chunks']}")
    print(f"  • Valid chunks: {stats['valid_chunks']}")
    print(f"  • Invalid chunks: {stats['invalid_chunks']}")
    print()
    
    print(f"📁 Projects:")
    for project, count in sorted(stats["projects"].items()):
        num_files = len(stats["files_by_project"][project])
        print(f"  • {project}: {count} chunks from {num_files} files")
    print()
    
    print(f"📄 Chunks per file:")
    for file_path, file_stats in sorted(stats["chunks_by_file"].items()):
        status = "✅" if file_stats["invalid"] == 0 else "⚠️"
        print(f"  {status} {file_path}: {file_stats['total']} chunks")
    print()
    
    # Check if ready for Script 2
    print("=" * 80)
    print("Script 2 Readiness Check")
    print("=" * 80)
    print()
    
    all_valid = stats["invalid_chunks"] == 0
    has_chunks = stats["total_chunks"] > 0
    
    if all_valid and has_chunks:
        print("✅ All checks passed!")
        print()
        print("The chunked data is valid and ready for Script 2.")
        print()
        print("Next step:")
        print("  python -m src.script2_generate_verify \\")
        print("    --workspace ./workspace \\")
        print("    --config ./config/app.config.yaml \\")
        print("    --parallel 2 \\")
        print("    --verbose")
        print()
        return True
    else:
        print("❌ Validation failed!")
        print()
        if not has_chunks:
            print("  • No chunks found")
        if not all_valid:
            print(f"  • {stats['invalid_chunks']} invalid chunks found")
            print()
            print("Errors:")
            for error in stats["errors"][:10]:  # Show first 10 errors
                print(f"  {error}")
            if len(stats["errors"]) > 10:
                print(f"  ... and {len(stats['errors']) - 10} more errors")
        print()
        return False


def show_sample_chunk(workspace_path: Path):
    """Show a sample chunk for inspection."""
    print("=" * 80)
    print("Sample Chunk Data")
    print("=" * 80)
    print()
    
    chunks_dir = workspace_path / "chunks"
    chunk_files = find_files(chunks_dir, "**/*.chunks.jsonl")
    
    if not chunk_files:
        print("No chunk files found")
        return
    
    # Read first chunk from first file
    chunk_file = sorted(chunk_files)[0]
    print(f"📄 File: {chunk_file.relative_to(chunks_dir)}")
    print()
    
    with open(chunk_file, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    
    chunk = json.loads(first_line)
    
    print("📋 Chunk Structure:")
    print(f"  • chunk_id: {chunk['chunk_id'][:50]}...")
    print(f"  • project: {chunk['project']}")
    print(f"  • file_path: {chunk['file_path']}")
    print(f"  • file_name: {chunk['file_name']}")
    print(f"  • chunk_index: {chunk['chunk_index']}")
    print(f"  • total_chunks: {chunk['total_chunks']}")
    print(f"  • token_start: {chunk['token_start']}")
    print(f"  • token_end: {chunk['token_end']}")
    print(f"  • text length: {len(chunk['text'])} characters")
    print(f"  • metadata:")
    for key, value in chunk['metadata'].items():
        if key == 'created_at':
            print(f"    - {key}: {value}")
        else:
            print(f"    - {key}: {value}")
    print()
    
    print("📝 Text Preview (first 500 characters):")
    print("-" * 80)
    print(chunk['text'][:500])
    if len(chunk['text']) > 500:
        print("...")
    print("-" * 80)
    print()
    
    print("✅ Chunk structure is valid and matches expected schema")
    print()


if __name__ == "__main__":
    workspace = Path("./workspace")
    
    # Show sample chunk
    show_sample_chunk(workspace)
    
    # Verify all chunks
    success = verify_chunks(workspace)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

