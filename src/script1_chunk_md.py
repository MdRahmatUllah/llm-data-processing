"""Script 1: Chunk markdown files into overlapping segments.

Usage:
    # Process all projects in input directory (auto-discovery)
    python -m src.script1_chunk_md --input-root ./input --workspace ./workspace --config ./config/app.config.yaml

    # Process a specific project
    python -m src.script1_chunk_md --input-root ./input --workspace ./workspace --config ./config/app.config.yaml
"""

import re
import click
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from tqdm import tqdm

from .common.config import load_config, Config
from .common.tokenizers import get_tokenizer, BaseTokenizer
from .common.hashing import compute_chunk_id, compute_file_sha1
from .common.io_utils import JSONLWriter, ensure_dir, find_files, setup_logger
from .common.validation import validate_chunk

logger = logging.getLogger(__name__)


class MarkdownChunker:
    """Chunk markdown files with semantic breaks and overlap."""
    
    def __init__(self, config: Config, tokenizer: BaseTokenizer):
        """
        Initialize chunker.
        
        Args:
            config: Configuration object
            tokenizer: Tokenizer instance
        """
        self.config = config
        self.tokenizer = tokenizer
        self.max_tokens = config.chunking.max_tokens_per_chunk
        self.overlap = config.chunking.overlap_tokens
        self.semantic_breaks_enabled = config.chunking.semantic_breaks.get('enabled', True)
        self.prefer_headings = config.chunking.semantic_breaks.get('prefer_headings', True)
        self.tolerance_pct = config.chunking.semantic_breaks.get('tolerance_pct', 10)
        
        logger.info(
            f"MarkdownChunker initialized: max_tokens={self.max_tokens}, "
            f"overlap={self.overlap}, semantic_breaks={self.semantic_breaks_enabled}"
        )
    
    def _find_semantic_breaks(self, text: str) -> list[int]:
        """
        Find character positions of semantic breaks.
        
        Priority order:
        1. ATX headings (# Header)
        2. Setext headings (underlined)
        3. Blank lines (paragraph breaks)
        
        Args:
            text: Full text
            
        Returns:
            Sorted list of character positions
        """
        breaks = []
        lines = text.split('\n')
        pos = 0
        
        for i, line in enumerate(lines):
            # ATX heading (# Header)
            if line.strip().startswith('#'):
                breaks.append((pos, 'heading'))
            # Setext heading (next line is === or ---)
            elif i > 0 and line.strip() and len(set(line.strip())) == 1:
                if line.strip()[0] in ('=', '-'):
                    # Mark the previous line as heading
                    prev_pos = pos - len(lines[i-1]) - 1
                    if prev_pos >= 0:
                        breaks.append((prev_pos, 'heading'))
            # Blank line (paragraph break)
            elif not line.strip() and pos > 0:
                breaks.append((pos, 'paragraph'))
            
            pos += len(line) + 1  # +1 for newline
        
        # Sort by position and remove duplicates
        breaks = sorted(set(breaks), key=lambda x: x[0])
        return [pos for pos, _ in breaks]
    
    def _find_best_break(
        self,
        text: str,
        token_ids: list[int],
        target_token: int,
        semantic_breaks: list[int]
    ) -> int:
        """
        Find best semantic break near target token position.
        
        Args:
            text: Full text
            token_ids: Token IDs for full text
            target_token: Target token position
            semantic_breaks: Character positions of semantic breaks
            
        Returns:
            Adjusted token position (or target if no good break found)
        """
        if not self.semantic_breaks_enabled or not semantic_breaks:
            return target_token
        
        # Calculate tolerance in tokens
        tolerance = int(self.max_tokens * (self.tolerance_pct / 100.0))
        min_token = max(0, target_token - tolerance)
        max_token = min(len(token_ids), target_token + tolerance)
        
        # Decode text up to max_token to find character positions
        try:
            text_up_to_max = self.tokenizer.decode(token_ids[:max_token])
            char_pos_max = len(text_up_to_max)
            
            # Find semantic breaks within character range
            text_up_to_min = self.tokenizer.decode(token_ids[:min_token])
            char_pos_min = len(text_up_to_min)
            
            # Find breaks in range
            breaks_in_range = [
                b for b in semantic_breaks
                if char_pos_min <= b <= char_pos_max
            ]
            
            if breaks_in_range:
                # Choose the break closest to target
                target_char = len(self.tokenizer.decode(token_ids[:target_token]))
                best_break = min(breaks_in_range, key=lambda b: abs(b - target_char))
                
                # Convert back to token position
                text_up_to_break = text[:best_break]
                adjusted_token = len(self.tokenizer.encode(text_up_to_break))
                
                logger.debug(
                    f"Adjusted chunk end from token {target_token} to {adjusted_token} "
                    f"(semantic break at char {best_break})"
                )
                return adjusted_token
        
        except Exception as e:
            logger.warning(f"Error finding semantic break: {e}")
        
        return target_token
    
    def _chunk_with_overlap(
        self,
        text: str,
        token_ids: list[int],
        semantic_breaks: list[int]
    ) -> list[tuple[int, int, str]]:
        """
        Create chunks with overlap.
        
        Args:
            text: Full text
            token_ids: Token IDs for full text
            semantic_breaks: Character positions of semantic breaks
            
        Returns:
            List of (token_start, token_end, chunk_text) tuples
        """
        chunks = []
        start_token = 0
        
        while start_token < len(token_ids):
            # Determine end token
            end_token = min(start_token + self.max_tokens, len(token_ids))
            
            # Adjust for semantic breaks if not at end of document
            if end_token < len(token_ids):
                end_token = self._find_best_break(text, token_ids, end_token, semantic_breaks)
            
            # Extract chunk text
            chunk_token_ids = token_ids[start_token:end_token]
            chunk_text = self.tokenizer.decode(chunk_token_ids)
            
            chunks.append((start_token, end_token, chunk_text))
            
            logger.debug(
                f"Created chunk: tokens [{start_token}, {end_token}), "
                f"length={end_token - start_token}, text_len={len(chunk_text)}"
            )
            
            # Next chunk starts with overlap
            if end_token >= len(token_ids):
                break
            
            start_token = end_token - self.overlap
            if start_token < 0:
                start_token = 0
        
        return chunks
    
    def chunk_file(self, file_path: Path, project: str) -> list[dict]:
        """
        Chunk a single markdown file.
        
        Args:
            file_path: Path to markdown file
            project: Project name
            
        Returns:
            List of chunk dictionaries
        """
        logger.info(f"Chunking file: {file_path}")
        
        # Read file
        text = file_path.read_text(encoding='utf-8')
        
        # Compute file hash
        file_sha1 = compute_file_sha1(str(file_path))
        
        # Find semantic breaks
        semantic_breaks = self._find_semantic_breaks(text) if self.semantic_breaks_enabled else []
        logger.debug(f"Found {len(semantic_breaks)} semantic breaks")
        
        # Tokenize
        token_ids = self.tokenizer.encode(text)
        logger.debug(f"File has {len(token_ids)} tokens")
        
        # Create chunks
        chunk_tuples = self._chunk_with_overlap(text, token_ids, semantic_breaks)
        logger.info(f"Created {len(chunk_tuples)} chunks")
        
        # Build chunk objects
        chunks = []
        for chunk_index, (token_start, token_end, chunk_text) in enumerate(chunk_tuples):
            # Compute relative path from input root
            try:
                file_relpath = str(file_path.relative_to(Path(self.config.input_root) / project))
            except ValueError:
                file_relpath = file_path.name
            
            # Generate chunk ID
            chunk_id = compute_chunk_id(project, file_relpath, chunk_index, file_sha1)
            
            # Build chunk object
            chunk = {
                "chunk_id": chunk_id,
                "project": project,
                "file_path": file_relpath,
                "file_name": file_path.name,
                "chunk_index": chunk_index,
                "total_chunks": len(chunk_tuples),
                "token_start": token_start,
                "token_end": token_end,
                "text": chunk_text,
                "metadata": {
                    "project_name": project,
                    "source_format": "markdown",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "file_sha1": file_sha1,
                    "tokenizer": self.config.chunking.tokenizer
                }
            }
            
            # Validate chunk
            is_valid, errors = validate_chunk(chunk)
            if not is_valid:
                logger.error(f"Chunk validation failed: {errors}")
                raise ValueError(f"Invalid chunk: {errors}")
            
            chunks.append(chunk)
        
        return chunks


def process_project(
    input_root: Path,
    project: str,
    workspace: Path,
    config: Config
) -> dict:
    """
    Process all markdown files in a project.
    
    Args:
        input_root: Input root directory
        project: Project name
        workspace: Workspace directory
        config: Configuration object
        
    Returns:
        Statistics dictionary
    """
    logger.info(f"Processing project: {project}")
    
    # Initialize tokenizer and chunker
    tokenizer = get_tokenizer(config.chunking.tokenizer)
    chunker = MarkdownChunker(config, tokenizer)
    
    # Find all markdown files
    project_dir = input_root / project
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    
    md_files = find_files(project_dir, "**/*.md")
    logger.info(f"Found {len(md_files)} markdown files")
    
    if not md_files:
        logger.warning(f"No markdown files found in {project_dir}")
        return {"files": 0, "chunks": 0}
    
    # Process each file
    total_chunks = 0
    
    for md_file in tqdm(md_files, desc="Chunking files"):
        try:
            # Chunk file
            chunks = chunker.chunk_file(md_file, project)
            
            # Determine output path
            try:
                rel_path = md_file.relative_to(project_dir)
            except ValueError:
                rel_path = Path(md_file.name)
            
            output_dir = workspace / "chunks" / project / rel_path.parent
            ensure_dir(output_dir)
            output_file = output_dir / f"{md_file.name}.chunks.jsonl"
            
            # Write chunks
            with JSONLWriter(output_file) as writer:
                for chunk in chunks:
                    writer.write_line(chunk)
            
            total_chunks += len(chunks)
            logger.debug(f"Wrote {len(chunks)} chunks to {output_file}")
        
        except Exception as e:
            logger.error(f"Error processing {md_file}: {e}", exc_info=True)
            raise
    
    logger.info(f"Processed {len(md_files)} files, created {total_chunks} chunks")
    
    return {
        "files": len(md_files),
        "chunks": total_chunks
    }


def discover_projects(input_root: Path) -> list[str]:
    """
    Discover all project directories in the input root.

    A project is any subdirectory that contains at least one .md file.

    Args:
        input_root: Input root directory

    Returns:
        List of project names (directory names)
    """
    projects = []

    if not input_root.exists():
        logger.warning(f"Input root does not exist: {input_root}")
        return projects

    # Find all subdirectories
    for item in input_root.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Check if directory contains any .md files
            md_files = list(item.glob("**/*.md"))
            if md_files:
                projects.append(item.name)
                logger.debug(f"Discovered project: {item.name} ({len(md_files)} markdown files)")

    return sorted(projects)


@click.command()
@click.option('--input-root', required=True, type=click.Path(exists=True), help='Input root directory')
@click.option('--project', default=None, help='Project name (optional; if not specified, all projects will be processed)')
@click.option('--workspace', required=True, type=click.Path(), help='Workspace directory')
@click.option('--config', required=True, type=click.Path(exists=True), help='Config file path')
@click.option('--verbose', is_flag=True, help='Enable debug logging')
def main(input_root: str, project: Optional[str], workspace: str, config: str, verbose: bool):
    """Chunk markdown files into overlapping segments.

    If --project is specified, only that project will be processed.
    If --project is not specified, all projects in the input root will be discovered and processed.
    """

    # Load config
    cfg = load_config(config)

    # Setup logging
    log_level = "DEBUG" if verbose else cfg.audit.log_level
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(cfg.audit.log_dir) / f"script1_{timestamp}.log"
    setup_logger(__name__, log_file, log_level)

    logger.info("=" * 80)
    logger.info("Script 1: Markdown Chunking")
    logger.info("=" * 80)
    logger.info(f"Input root: {input_root}")
    logger.info(f"Workspace: {workspace}")
    logger.info(f"Config: {config}")

    try:
        input_root_path = Path(input_root)
        workspace_path = Path(workspace)

        # Determine which projects to process
        if project:
            # Single project mode
            projects = [project]
            logger.info(f"Processing single project: {project}")
        else:
            # Auto-discovery mode
            logger.info("No project specified, discovering all projects...")
            projects = discover_projects(input_root_path)

            if not projects:
                logger.warning(f"No projects found in {input_root}")
                click.echo(f"No projects with markdown files found in {input_root}")
                return

            logger.info(f"Discovered {len(projects)} projects: {', '.join(projects)}")
            click.echo(f"\nDiscovered {len(projects)} projects:")
            for p in projects:
                click.echo(f"  - {p}")
            click.echo()

        # Process each project
        total_stats = {"files": 0, "chunks": 0, "projects": 0}

        for proj in projects:
            logger.info("-" * 80)
            logger.info(f"Processing project: {proj}")
            click.echo(f"Processing project: {proj}")

            try:
                stats = process_project(
                    input_root_path,
                    proj,
                    workspace_path,
                    cfg
                )

                total_stats["files"] += stats["files"]
                total_stats["chunks"] += stats["chunks"]
                total_stats["projects"] += 1

                logger.info(f"Project {proj}: {stats['files']} files, {stats['chunks']} chunks")
                click.echo(f"  ✓ {stats['files']} files, {stats['chunks']} chunks\n")

            except Exception as e:
                logger.error(f"Error processing project {proj}: {e}", exc_info=True)
                click.echo(f"  ✗ Error: {e}\n", err=True)
                # Continue with next project instead of failing completely
                continue

        # Final summary
        logger.info("=" * 80)
        logger.info("Chunking Complete")
        logger.info(f"Projects processed: {total_stats['projects']}/{len(projects)}")
        logger.info(f"Total files processed: {total_stats['files']}")
        logger.info(f"Total chunks created: {total_stats['chunks']}")
        logger.info("=" * 80)

        click.echo("=" * 80)
        click.echo("Chunking Complete")
        click.echo(f"Projects processed: {total_stats['projects']}/{len(projects)}")
        click.echo(f"Total files: {total_stats['files']}")
        click.echo(f"Total chunks: {total_stats['chunks']}")
        click.echo("=" * 80)

    except Exception as e:
        logger.error(f"Chunking failed: {e}", exc_info=True)
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()

