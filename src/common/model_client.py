"""Model API client with retry logic and rate limiting."""

import asyncio
import logging
from typing import Any, Optional
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .io_utils import RateLimiter

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""
    pass


class RateLimitError(APIError):
    """Exception for rate limit errors."""
    pass


class ModelClient:
    """Client for interacting with OpenAI-compatible model APIs."""
    
    def __init__(
        self,
        api_base: str,
        api_key: str,
        rate_limiter: Optional[RateLimiter] = None,
        timeout: int = 60,
        max_retries: int = 3,
        backoff_base: int = 2
    ):
        """
        Initialize model client.

        Args:
            api_base: Base URL for the API
            api_key: API key for authentication
            rate_limiter: Optional rate limiter
            timeout: Request timeout in seconds (used for read timeout)
            max_retries: Maximum number of retry attempts
            backoff_base: Base for exponential backoff (seconds)
        """
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base

        # Use granular timeout settings for better control
        # - connect: time to establish connection (short)
        # - read: time to wait for response data (long for LLM inference)
        # - write: time to send request data (short)
        # - pool: time to acquire connection from pool (short)
        timeout_config = httpx.Timeout(
            connect=10.0,      # 10 seconds to connect
            read=float(timeout),  # Main timeout for reading response
            write=10.0,        # 10 seconds to write request
            pool=5.0           # 5 seconds to get connection from pool
        )

        self.client = httpx.AsyncClient(
            timeout=timeout_config,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )

        logger.info(f"ModelClient initialized with base URL: {api_base}")
        logger.info(f"Timeout configuration: connect=10s, read={timeout}s, write=10s, pool=5s")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def generate(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> dict:
        """
        Generate completion from model.
        
        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for the API
            
        Returns:
            API response dictionary
            
        Raises:
            APIError: If API request fails
            RateLimitError: If rate limit is exceeded
        """
        # Acquire rate limit permission
        if self.rate_limiter:
            estimated_tokens = sum(len(m['content'].split()) * 1.3 for m in messages)
            estimated_tokens += max_tokens
            await self.rate_limiter.acquire(int(estimated_tokens))
        
        # Prepare request
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        logger.debug(f"API request to {url} with model {model}")
        
        try:
            response = await self.client.post(url, json=payload)
            
            # Handle rate limit errors
            if response.status_code == 429:
                logger.warning("Rate limit exceeded")
                raise RateLimitError("Rate limit exceeded")
            
            # Handle server errors
            if response.status_code >= 500:
                logger.error(f"Server error: {response.status_code}")
                raise APIError(f"Server error: {response.status_code}")
            
            # Handle client errors
            if response.status_code >= 400:
                error_msg = response.text
                logger.error(f"Client error: {response.status_code} - {error_msg}")
                raise APIError(f"Client error: {response.status_code} - {error_msg}")
            
            # Parse response
            result = response.json()
            logger.debug(f"API response received: {len(result.get('choices', []))} choices")
            
            return result
        
        except httpx.TimeoutException as e:
            # Provide more detailed timeout information
            timeout_type = "unknown"
            if "ConnectTimeout" in str(type(e)):
                timeout_type = "connect"
            elif "ReadTimeout" in str(type(e)):
                timeout_type = "read"
            elif "WriteTimeout" in str(type(e)):
                timeout_type = "write"
            elif "PoolTimeout" in str(type(e)):
                timeout_type = "pool"

            error_msg = f"Request timeout ({timeout_type}): {e}. Current read timeout: {self.timeout}s. Consider increasing timeout_seconds in config."
            logger.error(error_msg)
            raise APIError(error_msg)

        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise APIError(f"Request error: {e}")
    
    async def generate_with_retry(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> dict:
        """
        Generate completion with automatic retry logic.
        
        Retries on rate limit errors and server errors with exponential backoff.
        
        Args:
            model: Model name
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            API response dictionary
        """
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=self.backoff_base, min=1, max=60),
            retry=retry_if_exception_type((RateLimitError, APIError)),
            reraise=True
        )
        async def _generate_with_retry():
            return await self.generate(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        
        try:
            return await _generate_with_retry()
        except Exception as e:
            logger.error(f"Failed after {self.max_retries} retries: {e}")
            raise


def create_model_client(
    api_base: str,
    api_key: str,
    max_requests_per_minute: int = 60,
    max_tokens_per_minute: int = 90000,
    timeout: int = 60,
    max_retries: int = 3,
    backoff_base: int = 2
) -> ModelClient:
    """
    Create a model client with rate limiting.
    
    Args:
        api_base: Base URL for the API
        api_key: API key for authentication
        max_requests_per_minute: Maximum requests per minute
        max_tokens_per_minute: Maximum tokens per minute
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        backoff_base: Exponential backoff base
        
    Returns:
        Configured ModelClient instance
    """
    rate_limiter = RateLimiter(
        max_requests_per_minute=max_requests_per_minute,
        max_tokens_per_minute=max_tokens_per_minute
    )
    
    return ModelClient(
        api_base=api_base,
        api_key=api_key,
        rate_limiter=rate_limiter,
        timeout=timeout,
        max_retries=max_retries,
        backoff_base=backoff_base
    )

