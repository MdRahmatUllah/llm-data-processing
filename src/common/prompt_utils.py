"""Jinja2 template rendering utilities for prompts."""

import logging
from pathlib import Path
from typing import Any, Optional
import jinja2

logger = logging.getLogger(__name__)

# Global template cache
_template_cache: dict[str, jinja2.Template] = {}


def load_template(template_path: str) -> jinja2.Template:
    """
    Load and cache Jinja2 template.
    
    Args:
        template_path: Path to template file
        
    Returns:
        Compiled Jinja2 template
        
    Raises:
        FileNotFoundError: If template file doesn't exist
        
    Examples:
        >>> template = load_template("config/prompts/sft_user.jinja")
        >>> result = template.render(n=2, chunk_text="...")
    """
    if template_path in _template_cache:
        logger.debug(f"Using cached template: {template_path}")
        return _template_cache[template_path]
    
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        template_str = f.read()
    
    template = jinja2.Template(template_str)
    _template_cache[template_path] = template
    
    logger.debug(f"Loaded template: {template_path}")
    return template


def load_text_file(file_path: str) -> str:
    """
    Load text file (for system prompts).
    
    Args:
        file_path: Path to text file
        
    Returns:
        File contents as string
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    return path.read_text(encoding='utf-8').strip()


def render_generation_prompt(
    chunk: dict,
    system_prompt_file: str,
    user_prompt_template: str,
    n: int = 2
) -> list[dict]:
    """
    Render generation prompt from chunk.
    
    Args:
        chunk: Chunk dictionary
        system_prompt_file: Path to system prompt file
        user_prompt_template: Path to user prompt template
        n: Number of items to generate
        
    Returns:
        List of message dictionaries for API
        
    Examples:
        >>> messages = render_generation_prompt(chunk, "config/prompts/sft_system.txt", ...)
        >>> len(messages)
        2
        >>> messages[0]['role']
        'system'
    """
    # Load system prompt
    system_prompt = load_text_file(system_prompt_file)
    
    # Load and render user prompt template
    template = load_template(user_prompt_template)
    user_prompt = template.render(
        n=n,
        project=chunk.get('project', ''),
        file_name=chunk.get('file_name', ''),
        chunk_index=chunk.get('chunk_index', 0),
        chunk_id=chunk.get('chunk_id', ''),
        chunk_text=chunk.get('text', '')
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    logger.debug(f"Rendered generation prompt for chunk {chunk.get('chunk_id', 'unknown')}")
    return messages


def render_verification_prompt(
    item: dict,
    chunk: dict,
    system_prompt_file: str,
    user_prompt_template: str
) -> list[dict]:
    """
    Render verification prompt from item and chunk.
    
    Args:
        item: Generated item dictionary
        chunk: Source chunk dictionary
        system_prompt_file: Path to system prompt file
        user_prompt_template: Path to user prompt template
        
    Returns:
        List of message dictionaries for API
        
    Examples:
        >>> messages = render_verification_prompt(item, chunk, "config/prompts/...", ...)
        >>> messages[0]['role']
        'system'
    """
    import json
    
    # Load system prompt
    system_prompt = load_text_file(system_prompt_file)
    
    # Prepare chunk metadata
    chunk_meta = {
        'project': chunk.get('project', ''),
        'file_name': chunk.get('file_name', ''),
        'chunk_index': chunk.get('chunk_index', 0),
        'chunk_id': chunk.get('chunk_id', '')
    }
    
    # Load and render user prompt template
    template = load_template(user_prompt_template)
    user_prompt = template.render(
        candidate_json=json.dumps(item, indent=2, ensure_ascii=False),
        chunk_meta=chunk_meta,
        chunk_text=chunk.get('text', '')
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    logger.debug(f"Rendered verification prompt for item {item.get('id', 'unknown')}")
    return messages


def clear_template_cache() -> None:
    """Clear the global template cache."""
    global _template_cache
    _template_cache.clear()
    logger.debug("Cleared template cache")


def render_template_string(template_str: str, **kwargs) -> str:
    """
    Render a template string with variables.
    
    Args:
        template_str: Template string
        **kwargs: Variables to render
        
    Returns:
        Rendered string
        
    Examples:
        >>> render_template_string("Hello {{ name }}!", name="World")
        'Hello World!'
    """
    template = jinja2.Template(template_str)
    return template.render(**kwargs)

