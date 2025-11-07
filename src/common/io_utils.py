"""I/O utilities for file operations and rate limiting."""

import json
import logging
import asyncio
import time
from pathlib import Path
from typing import Iterator, Optional
from contextlib import contextmanager
from tqdm import tqdm

logger = logging.getLogger(__name__)


class JSONLWriter:
    """Write JSONL files with atomic operations."""
    
    def __init__(self, file_path: Path):
        """
        Initialize JSONL writer.
        
        Args:
            file_path: Path to output file
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = None
    
    def __enter__(self):
        """Open file for writing."""
        self.file = open(self.file_path, 'w', encoding='utf-8')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close file."""
        if self.file:
            self.file.close()
    
    def write_line(self, data: dict) -> None:
        """
        Write single JSON object as line.
        
        Args:
            data: Dictionary to write as JSON
        """
        line = json.dumps(data, ensure_ascii=False)
        self.file.write(line + '\n')
        self.file.flush()


class JSONLReader:
    """Read JSONL files line by line."""
    
    def __init__(self, file_path: Path):
        """
        Initialize JSONL reader.
        
        Args:
            file_path: Path to input file
        """
        self.file_path = Path(file_path)
        self.file = None
    
    def __enter__(self):
        """Open file for reading."""
        self.file = open(self.file_path, 'r', encoding='utf-8')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close file."""
        if self.file:
            self.file.close()
    
    def read_lines(self) -> Iterator[dict]:
        """
        Iterate over JSON objects.
        
        Yields:
            Dictionary for each valid JSON line
            
        Raises:
            json.JSONDecodeError: If a line contains invalid JSON
        """
        for line_num, line in enumerate(self.file, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON at {self.file_path}:{line_num}: {e}")
                raise


class RateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(
        self,
        max_requests_per_minute: int,
        max_tokens_per_minute: int
    ):
        """
        Initialize rate limiter.
        
        Uses token bucket algorithm with separate buckets for requests and tokens.
        
        Args:
            max_requests_per_minute: Maximum number of requests per minute
            max_tokens_per_minute: Maximum number of tokens per minute
        """
        self.max_requests = max_requests_per_minute
        self.max_tokens = max_tokens_per_minute
        
        self.request_tokens = max_requests_per_minute
        self.token_tokens = max_tokens_per_minute
        
        self.last_update = time.time()
        self.lock = asyncio.Lock()
        
        logger.info(
            f"RateLimiter initialized: {max_requests_per_minute} req/min, "
            f"{max_tokens_per_minute} tokens/min"
        )
    
    async def acquire(self, estimated_tokens: int = 1000) -> None:
        """
        Acquire permission to make API call.
        
        Blocks until sufficient tokens are available in both buckets.
        
        Args:
            estimated_tokens: Estimated tokens for this request
        """
        async with self.lock:
            while True:
                now = time.time()
                elapsed = now - self.last_update
                
                # Refill buckets based on elapsed time
                self.request_tokens = min(
                    self.max_requests,
                    self.request_tokens + (elapsed / 60.0) * self.max_requests
                )
                self.token_tokens = min(
                    self.max_tokens,
                    self.token_tokens + (elapsed / 60.0) * self.max_tokens
                )
                self.last_update = now
                
                # Check if we can proceed
                if self.request_tokens >= 1 and self.token_tokens >= estimated_tokens:
                    self.request_tokens -= 1
                    self.token_tokens -= estimated_tokens
                    logger.debug(
                        f"Rate limit acquired: {estimated_tokens} tokens "
                        f"(remaining: {self.request_tokens:.1f} req, "
                        f"{self.token_tokens:.1f} tokens)"
                    )
                    return
                
                # Wait and retry
                await asyncio.sleep(0.1)


def ensure_dir(path: Path) -> None:
    """
    Create directory if it doesn't exist.
    
    Args:
        path: Directory path to create
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def read_text_file(path: Path) -> str:
    """
    Read text file with UTF-8 encoding.
    
    Args:
        path: File path to read
        
    Returns:
        File contents as string
    """
    return Path(path).read_text(encoding='utf-8')


def write_text_file(path: Path, content: str) -> None:
    """
    Write text file with UTF-8 encoding.
    
    Creates parent directories if needed.
    
    Args:
        path: File path to write
        content: Content to write
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def find_files(root: Path, pattern: str) -> list[Path]:
    """
    Recursively find files matching pattern.
    
    Args:
        root: Root directory to search
        pattern: Glob pattern (e.g., "*.md", "**/*.jsonl")
        
    Returns:
        Sorted list of matching file paths
        
    Examples:
        >>> files = find_files(Path("input"), "**/*.md")
        >>> len(files)
        10
    """
    return sorted(Path(root).rglob(pattern))


def setup_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: str = "INFO"
) -> logging.Logger:
    """
    Set up logger with file and console handlers.
    
    Args:
        name: Logger name
        log_file: Optional log file path
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def count_jsonl_lines(file_path: Path) -> int:
    """
    Count non-empty lines in a JSONL file.
    
    Args:
        file_path: Path to JSONL file
        
    Returns:
        Number of non-empty lines
    """
    count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                count += 1
    return count

