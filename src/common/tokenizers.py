"""Tokenization utilities supporting multiple backends."""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BaseTokenizer(ABC):
    """Abstract base class for tokenizers."""
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to tokenize
            
        Returns:
            Number of tokens
        """
        pass
    
    @abstractmethod
    def encode(self, text: str) -> list[int]:
        """
        Encode text to token IDs.
        
        Args:
            text: Text to encode
            
        Returns:
            List of token IDs
        """
        pass
    
    def decode(self, token_ids: list[int]) -> str:
        """
        Decode token IDs to text (optional).
        
        Args:
            token_ids: List of token IDs
            
        Returns:
            Decoded text
            
        Raises:
            NotImplementedError: If decoder not implemented
        """
        raise NotImplementedError("Decoder not implemented")


class TiktokenTokenizer(BaseTokenizer):
    """Tokenizer using tiktoken library (OpenAI tokenizers)."""
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        Initialize tiktoken tokenizer.
        
        Args:
            encoding_name: Name of the encoding (e.g., "cl100k_base" for GPT-4)
            
        Raises:
            ImportError: If tiktoken is not installed
        """
        try:
            import tiktoken
            self.encoding = tiktoken.get_encoding(encoding_name)
            self.encoding_name = encoding_name
            logger.debug(f"Initialized TiktokenTokenizer with encoding: {encoding_name}")
        except ImportError:
            raise ImportError(
                "tiktoken not installed. Install with: pip install tiktoken"
            )
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
    
    def encode(self, text: str) -> list[int]:
        """Encode text to token IDs."""
        return self.encoding.encode(text)
    
    def decode(self, token_ids: list[int]) -> str:
        """Decode token IDs to text."""
        return self.encoding.decode(token_ids)
    
    def __repr__(self) -> str:
        return f"TiktokenTokenizer(encoding={self.encoding_name})"


class SentencePieceTokenizer(BaseTokenizer):
    """Tokenizer using SentencePiece library."""
    
    def __init__(self, model_path: str):
        """
        Initialize SentencePiece tokenizer.
        
        Args:
            model_path: Path to the SentencePiece model file
            
        Raises:
            ImportError: If sentencepiece is not installed
            FileNotFoundError: If model file doesn't exist
        """
        try:
            import sentencepiece as spm
            self.sp = spm.SentencePieceProcessor()
            self.sp.load(model_path)
            self.model_path = model_path
            logger.debug(f"Initialized SentencePieceTokenizer with model: {model_path}")
        except ImportError:
            raise ImportError(
                "sentencepiece not installed. Install with: pip install sentencepiece"
            )
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.sp.encode(text))
    
    def encode(self, text: str) -> list[int]:
        """Encode text to token IDs."""
        return self.sp.encode(text)
    
    def decode(self, token_ids: list[int]) -> str:
        """Decode token IDs to text."""
        return self.sp.decode(token_ids)
    
    def __repr__(self) -> str:
        return f"SentencePieceTokenizer(model={self.model_path})"


# Global tokenizer cache
_tokenizer_cache: dict[str, BaseTokenizer] = {}


def get_tokenizer(config_str: str) -> BaseTokenizer:
    """
    Get or create tokenizer from config string.
    
    Tokenizers are cached globally to avoid reloading.
    
    Supported formats:
    - "cl100k_base" or "cl100k-like" -> TiktokenTokenizer with cl100k_base
    - "gpt2" -> TiktokenTokenizer with gpt2 encoding
    - "sentencepiece:model=/path/to/model.model" -> SentencePieceTokenizer
    
    Args:
        config_str: Tokenizer configuration string
        
    Returns:
        Tokenizer instance (cached)
        
    Raises:
        ValueError: If config string format is invalid
        
    Examples:
        >>> tokenizer = get_tokenizer("cl100k_base")
        >>> tokenizer.count_tokens("hello world")
        2
    """
    if config_str in _tokenizer_cache:
        logger.debug(f"Using cached tokenizer: {config_str}")
        return _tokenizer_cache[config_str]
    
    # Parse config string and create tokenizer
    if config_str in ("cl100k_base", "cl100k-like"):
        tokenizer = TiktokenTokenizer("cl100k_base")
    elif config_str == "gpt2":
        tokenizer = TiktokenTokenizer("gpt2")
    elif config_str.startswith("sentencepiece:"):
        # Parse "sentencepiece:model=/path/to/model.model"
        parts = config_str.split(":", 1)[1]
        params = dict(p.split("=", 1) for p in parts.split(","))
        model_path = params.get("model")
        if not model_path:
            raise ValueError("SentencePiece config must include model=path")
        tokenizer = SentencePieceTokenizer(model_path)
    else:
        raise ValueError(f"Unknown tokenizer config: {config_str}")
    
    _tokenizer_cache[config_str] = tokenizer
    logger.info(f"Loaded tokenizer: {config_str}")
    return tokenizer


def clear_tokenizer_cache() -> None:
    """Clear the global tokenizer cache."""
    global _tokenizer_cache
    _tokenizer_cache.clear()
    logger.debug("Cleared tokenizer cache")

