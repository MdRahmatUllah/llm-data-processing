"""Configuration file loading and management."""

import yaml
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for chunking."""
    tokenizer: str
    max_tokens_per_chunk: int
    overlap_tokens: int
    semantic_breaks: dict = field(default_factory=dict)


@dataclass
class GenerationConfig:
    """Configuration for generation."""
    model_name: str
    temperature: float
    max_tokens: int
    system_prompt_file: str
    user_prompt_template: str
    items_per_chunk: int = 2


@dataclass
class VerificationConfig:
    """Configuration for verification."""
    enabled: bool
    model_name: str
    temperature: float
    max_tokens: int
    system_prompt_file: str
    user_prompt_template: str
    local_checks: list[str] = field(default_factory=list)


@dataclass
class PackingConfig:
    """Configuration for packing."""
    shuffle_seed: Optional[int]
    splits: dict[str, float]
    shard_size: int
    output_format: str = "jsonl"
    write_manifest: bool = True


@dataclass
class RuntimeConfig:
    """Runtime configuration."""
    max_requests_per_minute: int = 60
    max_tokens_per_minute: int = 90000
    parallel_chunks: int = 6
    retry_max_attempts: int = 3
    retry_backoff_base: int = 2
    timeout_seconds: int = 600


@dataclass
class AuditConfig:
    """Audit and logging configuration."""
    log_level: str = "INFO"
    log_dir: str = "./workspace/logs"
    save_rejected_items: bool = True
    save_verification_reports: bool = True
    save_manifest: bool = True


@dataclass
class Config:
    """Main configuration class."""
    project_name: str
    input_root: str
    workspace_root: str
    output_root: str
    chunking: ChunkingConfig
    generation: GenerationConfig
    verification: VerificationConfig
    packing: PackingConfig
    metadata_defaults: dict = field(default_factory=dict)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    
    def __post_init__(self):
        """Resolve relative paths to absolute paths."""
        self.input_root = str(Path(self.input_root).resolve())
        self.workspace_root = str(Path(self.workspace_root).resolve())
        self.output_root = str(Path(self.output_root).resolve())
        self.audit.log_dir = str(Path(self.audit.log_dir).resolve())


def load_config(config_path: str) -> Config:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Config object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
        
    Examples:
        >>> config = load_config("config/app.config.yaml")
        >>> config.project_name
        'SyntheticDataset'
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Validate required fields
    required_fields = [
        'project_name', 'input_root', 'workspace_root', 'output_root',
        'chunking', 'generation', 'verification', 'packing'
    ]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field in config: {field}")
    
    # Parse nested configs
    chunking = ChunkingConfig(**data['chunking'])
    generation = GenerationConfig(**data['generation'])
    verification = VerificationConfig(**data['verification'])
    packing = PackingConfig(**data['packing'])
    
    # Parse optional configs
    runtime = RuntimeConfig(**data.get('runtime', {}))
    audit = AuditConfig(**data.get('audit', {}))
    
    config = Config(
        project_name=data['project_name'],
        input_root=data['input_root'],
        workspace_root=data['workspace_root'],
        output_root=data['output_root'],
        chunking=chunking,
        generation=generation,
        verification=verification,
        packing=packing,
        metadata_defaults=data.get('metadata_defaults', {}),
        runtime=runtime,
        audit=audit
    )
    
    logger.info(f"Loaded configuration from {config_path}")
    logger.debug(f"Project: {config.project_name}")
    logger.debug(f"Input root: {config.input_root}")
    logger.debug(f"Workspace root: {config.workspace_root}")
    logger.debug(f"Output root: {config.output_root}")
    
    return config


def validate_config(config: Config) -> list[str]:
    """
    Validate configuration for common issues.
    
    Args:
        config: Config object to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check paths exist
    if not Path(config.input_root).exists():
        errors.append(f"Input root does not exist: {config.input_root}")
    
    # Check chunking config
    if config.chunking.max_tokens_per_chunk <= 0:
        errors.append("max_tokens_per_chunk must be positive")
    if config.chunking.overlap_tokens < 0:
        errors.append("overlap_tokens must be non-negative")
    if config.chunking.overlap_tokens >= config.chunking.max_tokens_per_chunk:
        errors.append("overlap_tokens must be less than max_tokens_per_chunk")
    
    # Check generation config
    if config.generation.temperature < 0 or config.generation.temperature > 2:
        errors.append("generation temperature must be between 0 and 2")
    if config.generation.max_tokens <= 0:
        errors.append("generation max_tokens must be positive")
    
    # Check verification config
    if config.verification.enabled:
        if config.verification.temperature < 0 or config.verification.temperature > 2:
            errors.append("verification temperature must be between 0 and 2")
    
    # Check packing config
    if config.packing.shard_size <= 0:
        errors.append("shard_size must be positive")
    
    split_sum = sum(config.packing.splits.values())
    if abs(split_sum - 1.0) > 0.01:
        errors.append(f"Split ratios must sum to 1.0 (got {split_sum})")
    
    # Check runtime config
    if config.runtime.max_requests_per_minute <= 0:
        errors.append("max_requests_per_minute must be positive")
    if config.runtime.parallel_chunks <= 0:
        errors.append("parallel_chunks must be positive")
    
    return errors

