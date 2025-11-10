"""Script 2: Generate synthetic examples from chunks and verify them.
python -m src.script2_generate_verify --workspace ./workspace --config ./config/app.config.yaml --parallel 2 --verbose
"""

import os
import re
import json
import asyncio
import click
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from tqdm.asyncio import tqdm as async_tqdm
from dotenv import load_dotenv

from .common.config import load_config, Config
from .common.model_client import create_model_client, ModelClient
from .common.prompt_utils import render_generation_prompt, render_verification_prompt, load_text_file
from .common.ids import generate_uuid
from .common.io_utils import JSONLWriter, JSONLReader, ensure_dir, find_files, setup_logger
from .common.validation import validate_generated_item

logger = logging.getLogger(__name__)


class Generator:
    """Generate synthetic SFT examples from chunks."""
    
    def __init__(self, config: Config, model_client: ModelClient):
        """
        Initialize generator.
        
        Args:
            config: Configuration object
            model_client: Model API client
        """
        self.config = config
        self.model_client = model_client
        self.system_prompt = load_text_file(config.generation.system_prompt_file)
        
        logger.info(
            f"Generator initialized: model={config.generation.model_name}, "
            f"temperature={config.generation.temperature}, "
            f"items_per_chunk={config.generation.items_per_chunk}"
        )
    
    async def generate_from_chunk(self, chunk: dict) -> list[dict]:
        """
        Generate items from a single chunk.
        
        Args:
            chunk: Chunk dictionary
            
        Returns:
            List of generated items (1-2 items)
            
        Raises:
            Exception: If generation fails
        """
        chunk_id = chunk.get('chunk_id', 'unknown')
        logger.debug(f"Generating from chunk {chunk_id}")

        try:
            # Render prompt
            messages = render_generation_prompt(
                chunk=chunk,
                system_prompt_file=self.config.generation.system_prompt_file,
                user_prompt_template=self.config.generation.user_prompt_template,
                n=self.config.generation.items_per_chunk
            )

            # Call model API with retry logic for empty responses
            max_empty_retries = 3
            retry_delay = 2  # seconds

            for attempt in range(max_empty_retries):
                logger.info(f"Calling generation model {self.config.generation.model_name} for chunk {chunk_id[:16]}... (attempt {attempt + 1}/{max_empty_retries})")

                try:
                    response = await self.model_client.generate_with_retry(
                        model=self.config.generation.model_name,
                        messages=messages,
                        temperature=self.config.generation.temperature,
                        max_tokens=self.config.generation.max_tokens
                    )

                    # Extract content from response
                    content = response.get('choices', [{}])[0].get('message', {}).get('content', '')

                    # Check for empty or whitespace-only response
                    if not content or not content.strip():
                        logger.warning(f"Empty response received from model for chunk {chunk_id[:16]} (attempt {attempt + 1}/{max_empty_retries})")
                        logger.warning(f"Full API response: {response}")

                        # Save debug info for empty response
                        debug_path = Path(self.config.audit.log_dir) / "failed_json" / f"chunk_{chunk_id[:16]}_empty_attempt{attempt + 1}.txt"
                        debug_path.parent.mkdir(parents=True, exist_ok=True)

                        with open(debug_path, 'w', encoding='utf-8') as f:
                            f.write("=" * 80 + "\n")
                            f.write("EMPTY RESPONSE DEBUG INFO\n")
                            f.write("=" * 80 + "\n\n")
                            f.write(f"Chunk ID: {chunk_id}\n")
                            f.write(f"Attempt: {attempt + 1}/{max_empty_retries}\n")
                            f.write(f"Model: {self.config.generation.model_name}\n")
                            f.write(f"Temperature: {self.config.generation.temperature}\n")
                            f.write(f"Max Tokens: {self.config.generation.max_tokens}\n\n")
                            f.write("Full API Response:\n")
                            f.write("-" * 80 + "\n")
                            f.write(json.dumps(response, indent=2, ensure_ascii=False))
                            f.write("\n\n")
                            f.write("Chunk Content (first 1000 chars):\n")
                            f.write("-" * 80 + "\n")
                            f.write(chunk.get('content', '')[:1000])
                            f.write("\n")

                        logger.warning(f"Empty response debug info saved to: {debug_path}")

                        # If not the last attempt, wait and retry
                        if attempt < max_empty_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                            logger.info(f"Waiting {wait_time}s before retry...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Last attempt failed, raise error
                            error_msg = (
                                f"Model returned empty response after {max_empty_retries} attempts for chunk {chunk_id[:16]}. "
                                f"Possible causes: (1) Model timeout/interruption, (2) Context length issues, "
                                f"(3) Model refusing to generate for this content, (4) Ollama server resource exhaustion. "
                                f"Check debug file: {debug_path}"
                            )
                            logger.error(error_msg)
                            raise ValueError(error_msg)

                    # Valid non-empty response received
                    logger.info(f"Generation completed for chunk {chunk_id[:16]} (received {len(content)} chars)")
                    break  # Exit retry loop

                except Exception as e:
                    # If it's not an empty response issue, re-raise immediately
                    if "empty response" not in str(e).lower():
                        logger.error(f"API call failed for chunk {chunk_id[:16]}: {e}")
                        raise
                    # Otherwise, let the retry loop handle it
                    if attempt == max_empty_retries - 1:
                        raise

            # Parse response
            # Use robust JSON parsing with automatic sanitization
            try:
                from src.common.json_utils import parse_json_robust, save_failed_json

                logger.debug(f"Parsing JSON response (length: {len(content)} chars)")
                items_raw = parse_json_robust(
                    content,
                    sanitize=True,
                    extract_markdown=True
                )
                logger.debug(f"Successfully parsed JSON response")

            except json.JSONDecodeError as e:
                # Save failed JSON for debugging
                debug_path = Path(self.config.audit.log_dir) / "failed_json" / f"chunk_{chunk_id[:16]}.txt"
                save_failed_json(
                    content=content,
                    error=e,
                    output_path=str(debug_path),
                    context={
                        "chunk_id": chunk_id,
                        "model": self.config.generation.model_name,
                        "temperature": self.config.generation.temperature,
                        "max_tokens": self.config.generation.max_tokens,
                        "content_length": len(content),
                        "content_preview": content[:500] if content else "(empty)"
                    }
                )

                logger.error(f"Failed to parse JSON from model response for chunk {chunk_id}: {e}")
                logger.error(f"Error location: line {e.lineno} column {e.colno}")
                logger.error(f"Response content (first 500 chars): {content[:500] if content else '(empty)'}")
                logger.error(f"Debug info saved to: {debug_path}")
                raise

            # Ensure it's a list
            if not isinstance(items_raw, list):
                items_raw = [items_raw]

            # Convert to full item format
            items = []
            for item_raw in items_raw:
                # Validate that required fields are present
                if "problem" not in item_raw or "solution" not in item_raw:
                    logger.warning(f"Skipping item missing required fields: {list(item_raw.keys())}")
                    continue

                # Merge metadata defaults with chunk-specific metadata
                metadata = {
                    **self.config.metadata_defaults,
                    "project": chunk.get("project", ""),
                    "file_path": chunk.get("file_path", ""),
                    "file_name": chunk.get("file_name", ""),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "chunk_id": chunk.get("chunk_id", "")
                }

                item = {
                    "id": generate_uuid(),
                    "system_prompt": self.system_prompt,
                    "metadata": metadata,
                    "messages": [
                        {"role": "user", "content": item_raw["problem"]},
                        {"role": "assistant", "content": item_raw["solution"]}
                    ],
                    "problem": item_raw["problem"],
                    "solution": item_raw["solution"],
                    "created_at": datetime.utcnow().isoformat() + "Z"
                }
                items.append(item)

            if len(items) == 0:
                logger.warning(f"No valid items generated from chunk {chunk_id}")
            else:
                logger.info(f"Generated {len(items)} items from chunk {chunk_id}")

            return items

        except json.JSONDecodeError as e:
            # This should be caught above, but just in case
            logger.error(f"JSON parsing error for chunk {chunk_id}: {e}")
            raise
        
        except Exception as e:
            logger.error(f"Generation failed for chunk {chunk_id}: {e}")
            raise


class Verifier:
    """Verify generated items for quality and correctness."""
    
    def __init__(self, config: Config, model_client: Optional[ModelClient] = None):
        """
        Initialize verifier.
        
        Args:
            config: Configuration object
            model_client: Optional model API client (for model-based verification)
        """
        self.config = config
        self.model_client = model_client
        self.enabled = config.verification.enabled
        
        logger.info(
            f"Verifier initialized: enabled={self.enabled}, "
            f"local_checks={config.verification.local_checks}"
        )
    
    def _run_local_checks(self, item: dict, chunk: dict) -> dict:
        """
        Run local validation checks.

        Args:
            item: Generated item
            chunk: Source chunk

        Returns:
            Dictionary of check results (check_name -> bool)
        """
        checks = {}

        # Schema validation
        is_valid, errors = validate_generated_item(item)
        checks["json_schema_valid"] = is_valid
        if not is_valid:
            logger.debug(f"Schema validation failed: {errors}")

        # Messages shape
        messages = item.get("messages", [])
        checks["messages_shape_valid"] = (
            len(messages) == 2 and
            messages[0].get("role") == "user" and
            messages[1].get("role") == "assistant"
        )

        # Special tokens - check for both opening and closing tags
        solution = item.get("solution", "")

        # Check for thought section tags
        has_begin_thought = "<|begin_of_thought|>" in solution
        has_end_thought = "<|end_of_thought|>" in solution
        checks["has_thought_begin_token"] = has_begin_thought
        checks["has_thought_end_token"] = has_end_thought
        checks["thought_tags_properly_paired"] = has_begin_thought == has_end_thought

        # Check for solution section tags
        has_begin_solution = "<|begin_of_solution|>" in solution
        has_end_solution = "<|end_of_solution|>" in solution
        checks["has_solution_begin_token"] = has_begin_solution
        checks["has_solution_end_token"] = has_end_solution
        checks["solution_tags_properly_paired"] = has_begin_solution == has_end_solution

        # Check tag ordering (thought section should come before solution section)
        if has_begin_thought and has_begin_solution:
            thought_pos = solution.index("<|begin_of_thought|>")
            solution_pos = solution.index("<|begin_of_solution|>")
            checks["tags_in_correct_order"] = thought_pos < solution_pos
        else:
            checks["tags_in_correct_order"] = False

        # Check that closing tags come after opening tags (proper nesting)
        if has_begin_thought and has_end_thought:
            begin_pos = solution.index("<|begin_of_thought|>")
            end_pos = solution.index("<|end_of_thought|>")
            checks["thought_tags_properly_nested"] = begin_pos < end_pos
        else:
            checks["thought_tags_properly_nested"] = has_begin_thought == has_end_thought

        if has_begin_solution and has_end_solution:
            begin_pos = solution.index("<|begin_of_solution|>")
            end_pos = solution.index("<|end_of_solution|>")
            checks["solution_tags_properly_nested"] = begin_pos < end_pos
        else:
            checks["solution_tags_properly_nested"] = has_begin_solution == has_end_solution

        # Boxed answer (if required)
        system_prompt = item.get("system_prompt", "")
        # if "\\boxed" in system_prompt or "boxed" in system_prompt.lower():
        #     checks["final_answer_boxed_if_required"] = bool(re.search(r'\\boxed\{[^}]+\}', solution))
        # else:
        checks["final_answer_boxed_if_required"] = True

        return checks
    
    async def verify_item(self, item: dict, chunk: dict) -> dict:
        """
        Verify a generated item.
        
        Args:
            item: Generated item
            chunk: Source chunk
            
        Returns:
            Verification report dictionary
        """
        item_id = item.get("id", "unknown")
        chunk_id = chunk.get("chunk_id", "unknown")
        
        logger.debug(f"Verifying item {item_id}")
        
        # Run local checks
        checks = self._run_local_checks(item, chunk)
        
        # Collect errors from failed checks
        errors = [check_name for check_name, passed in checks.items() if not passed]
        
        # If local checks fail or model verification disabled, return early
        if errors or not self.enabled or not self.model_client:
            report = {
                "input_item_id": item_id,
                "chunk_id": chunk_id,
                "passed": len(errors) == 0,
                "errors": errors,
                "checks": checks,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            
            if errors:
                logger.debug(f"Item {item_id} failed local checks: {errors}")
            
            return report
        
        # Model-based verification
        try:
            messages = render_verification_prompt(
                item=item,
                chunk=chunk,
                system_prompt_file=self.config.verification.system_prompt_file,
                user_prompt_template=self.config.verification.user_prompt_template
            )

            logger.info(f"Calling verification model {self.config.verification.model_name} for item {item_id[:16]}...")
            response = await self.model_client.generate_with_retry(
                model=self.config.verification.model_name,
                messages=messages,
                temperature=self.config.verification.temperature,
                max_tokens=self.config.verification.max_tokens
            )
            logger.info(f"Verification completed for item {item_id[:16]}...")
            
            # Parse verifier response
            content = response['choices'][0]['message']['content']

            # Use robust JSON parsing
            try:
                from src.common.json_utils import parse_json_robust, save_failed_json

                verifier_result = parse_json_robust(
                    content,
                    sanitize=True,
                    extract_markdown=True
                )

            except json.JSONDecodeError as e:
                # Save failed JSON for debugging
                debug_path = Path(self.config.audit.log_dir) / "failed_json" / f"verifier_{item_id[:16]}.txt"
                save_failed_json(
                    content=content,
                    error=e,
                    output_path=str(debug_path),
                    context={
                        "item_id": item_id,
                        "chunk_id": chunk_id,
                        "model": self.config.verification.model_name,
                        "stage": "verification"
                    }
                )

                logger.error(f"Failed to parse verifier JSON for item {item_id}: {e}")
                logger.error(f"Debug info saved to: {debug_path}")

                # Fall back to local checks only
                return {
                    "input_item_id": item_id,
                    "chunk_id": chunk_id,
                    "passed": len(errors) == 0,
                    "errors": errors + [f"Verifier JSON parse error: {str(e)}"],
                    "checks": checks,
                    "created_at": datetime.utcnow().isoformat() + "Z"
                }
            
            # Merge with local checks
            model_passed = verifier_result.get("passed", False)
            model_errors = verifier_result.get("errors", [])
            
            report = {
                "input_item_id": item_id,
                "chunk_id": chunk_id,
                "passed": model_passed and len(errors) == 0,
                "errors": errors + model_errors,
                "checks": {
                    **checks,
                    "content_consistent_with_chunk": model_passed
                },
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            
            if not report["passed"]:
                logger.debug(f"Item {item_id} failed verification: {report['errors']}")
            
            return report
        
        except Exception as e:
            logger.error(f"Model verification failed for item {item_id}: {e}")
            # Fall back to local checks only
            return {
                "input_item_id": item_id,
                "chunk_id": chunk_id,
                "passed": len(errors) == 0,
                "errors": errors + [f"Model verification error: {str(e)}"],
                "checks": checks,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }


async def process_chunk(
    chunk: dict,
    generator: Generator,
    verifier: Verifier,
    workspace: Path,
    config: Config
) -> dict:
    """
    Process a single chunk: generate and verify items.
    
    Args:
        chunk: Chunk dictionary
        generator: Generator instance
        verifier: Verifier instance
        workspace: Workspace directory
        config: Configuration object
        
    Returns:
        Statistics dictionary
    """
    chunk_id = chunk.get("chunk_id", "unknown")
    project = chunk.get("project", "unknown")
    file_path = chunk.get("file_path", "")
    chunk_index = chunk.get("chunk_index", 0)
    
    logger.debug(f"Processing chunk {chunk_id}")
    
    stats = {
        "chunk_id": chunk_id,
        "generated_count": 0,
        "verified_count": 0,
        "rejected_count": 0
    }
    
    try:
        # Generate items
        items = await generator.generate_from_chunk(chunk)
        stats["generated_count"] = len(items)
        
        # Prepare output paths
        rel_dir = Path(file_path).parent if file_path else Path(".")
        
        generations_dir = workspace / "generations" / project / rel_dir
        verified_dir = workspace / "verified" / project / rel_dir
        rejected_dir = workspace / "rejected" / project / rel_dir
        
        ensure_dir(generations_dir)
        ensure_dir(verified_dir)
        ensure_dir(rejected_dir)
        
        generations_file = generations_dir / f"chunk-{chunk_index:04d}.jsonl"
        verified_file = verified_dir / f"chunk-{chunk_index:04d}.verified.jsonl"
        rejected_file = rejected_dir / f"chunk-{chunk_index:04d}.rejected.jsonl"
        
        # Write generated items
        with JSONLWriter(generations_file) as writer:
            for item in items:
                writer.write_line(item)
        
        # Verify each item
        verified_items = []
        rejected_items = []
        
        for item in items:
            verify_report = await verifier.verify_item(item, chunk)
            
            if verify_report["passed"]:
                verified_items.append(item)
                stats["verified_count"] += 1
            else:
                rejected_items.append({
                    "item": item,
                    "verify_report": verify_report
                })
                stats["rejected_count"] += 1
        
        # Write verified items
        if verified_items:
            with JSONLWriter(verified_file) as writer:
                for item in verified_items:
                    writer.write_line(item)
        
        # Write rejected items (if configured)
        if rejected_items and config.audit.save_rejected_items:
            with JSONLWriter(rejected_file) as writer:
                for rejected in rejected_items:
                    writer.write_line(rejected)
        
        logger.info(
            f"Chunk {chunk_id}: generated={stats['generated_count']}, "
            f"verified={stats['verified_count']}, rejected={stats['rejected_count']}"
        )
        
        return stats

    except Exception as e:
        logger.error(f"Failed to process chunk {chunk_id}: {e}", exc_info=True)

        # Save error info to a dedicated error log file
        error_dir = workspace / "logs" / "failed_chunks"
        error_dir.mkdir(parents=True, exist_ok=True)
        error_file = error_dir / f"chunk_{chunk_id[:16]}_error.txt"

        with open(error_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("CHUNK PROCESSING ERROR\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Chunk ID: {chunk_id}\n")
            f.write(f"Project: {project}\n")
            f.write(f"File: {file_path}\n")
            f.write(f"Chunk Index: {chunk_index}\n\n")
            f.write(f"Error Type: {type(e).__name__}\n")
            f.write(f"Error Message: {str(e)}\n\n")
            f.write("Chunk Content (first 1000 chars):\n")
            f.write("-" * 80 + "\n")
            f.write(chunk.get('content', '')[:1000])
            f.write("\n")

        logger.error(f"Error details saved to: {error_file}")

        # Return stats with zero counts to allow pipeline to continue
        return stats


async def process_all_chunks(
    workspace: Path,
    config: Config,
    parallelism: int,
    resume: bool = False
) -> dict:
    """
    Process all chunks in workspace.

    Args:
        workspace: Workspace directory
        config: Configuration object
        parallelism: Number of concurrent chunk processors
        resume: Skip already processed chunks

    Returns:
        Aggregated statistics
    """
    logger.info("=" * 80)
    logger.info("Finding chunks to process...")

    # Find all chunk files
    chunks_dir = workspace / "chunks"
    chunk_files = find_files(chunks_dir, "**/*.chunks.jsonl")

    if not chunk_files:
        logger.warning(f"No chunk files found in {chunks_dir}")
        return {
            "total_chunks": 0,
            "total_generated": 0,
            "total_verified": 0,
            "total_rejected": 0
        }

    logger.info(f"Found {len(chunk_files)} chunk files")

    # Load all chunks
    all_chunks = []
    for chunk_file in chunk_files:
        with JSONLReader(chunk_file) as reader:
            for chunk in reader.read_lines():
                all_chunks.append(chunk)

    logger.info(f"Loaded {len(all_chunks)} chunks")

    # Filter out already processed chunks if resuming
    if resume:
        chunks_to_process = []
        for chunk in all_chunks:
            project = chunk.get("project", "unknown")
            file_path = chunk.get("file_path", "")
            chunk_index = chunk.get("chunk_index", 0)
            rel_dir = Path(file_path).parent if file_path else Path(".")

            verified_file = workspace / "verified" / project / rel_dir / f"chunk-{chunk_index:04d}.verified.jsonl"

            if not verified_file.exists():
                chunks_to_process.append(chunk)

        logger.info(f"Resume mode: {len(chunks_to_process)} chunks remaining (skipped {len(all_chunks) - len(chunks_to_process)})")
        all_chunks = chunks_to_process

    if not all_chunks:
        logger.info("No chunks to process")
        return {
            "total_chunks": 0,
            "total_generated": 0,
            "total_verified": 0,
            "total_rejected": 0
        }

    # Get API credentials from environment
    api_base = os.getenv("MODEL_API_BASE", "http://localhost:8000/v1")
    api_key = os.getenv("MODEL_API_KEY", "dummy-key")

    # Create model clients
    logger.info("Initializing model clients...")

    gen_client = create_model_client(
        api_base=api_base,
        api_key=api_key,
        max_requests_per_minute=config.runtime.max_requests_per_minute,
        max_tokens_per_minute=config.runtime.max_tokens_per_minute,
        timeout=config.runtime.timeout_seconds,
        max_retries=config.runtime.retry_max_attempts,
        backoff_base=config.runtime.retry_backoff_base
    )

    # Create verifier client if verification enabled
    ver_client = None
    if config.verification.enabled:
        ver_client = create_model_client(
            api_base=api_base,
            api_key=api_key,
            max_requests_per_minute=config.runtime.max_requests_per_minute,
            max_tokens_per_minute=config.runtime.max_tokens_per_minute,
            timeout=config.runtime.timeout_seconds,
            max_retries=config.runtime.retry_max_attempts,
            backoff_base=config.runtime.retry_backoff_base
        )

    # Create generator and verifier
    generator = Generator(config, gen_client)
    verifier = Verifier(config, ver_client)

    # Process chunks in parallel with semaphore
    semaphore = asyncio.Semaphore(parallelism)

    async def process_with_semaphore(chunk):
        async with semaphore:
            return await process_chunk(chunk, generator, verifier, workspace, config)

    # Process all chunks with progress bar
    logger.info(f"Processing {len(all_chunks)} chunks with parallelism={parallelism}...")

    tasks = [process_with_semaphore(chunk) for chunk in all_chunks]
    results = []
    failed_chunks = []

    # Use tqdm for progress tracking
    for coro in async_tqdm.as_completed(tasks, total=len(tasks), desc="Processing chunks"):
        try:
            result = await coro
            results.append(result)

            # Track chunks that generated 0 items (likely failed)
            if result.get("generated_count", 0) == 0:
                failed_chunks.append(result.get("chunk_id", "unknown"))
        except Exception as e:
            logger.error(f"Chunk processing failed: {e}")
            failed_chunks.append("unknown")
            # Continue with other chunks

    # Close clients
    await gen_client.close()
    if ver_client:
        await ver_client.close()

    # Aggregate statistics
    total_stats = {
        "total_chunks": len(results),
        "total_generated": sum(r["generated_count"] for r in results),
        "total_verified": sum(r["verified_count"] for r in results),
        "total_rejected": sum(r["rejected_count"] for r in results),
        "failed_chunks": len(failed_chunks)
    }

    logger.info("=" * 80)
    logger.info("Processing Complete")
    logger.info(f"Chunks processed: {total_stats['total_chunks']}")
    logger.info(f"Items generated: {total_stats['total_generated']}")
    logger.info(f"Items verified: {total_stats['total_verified']}")
    logger.info(f"Items rejected: {total_stats['total_rejected']}")

    if failed_chunks:
        logger.warning(f"Failed chunks: {total_stats['failed_chunks']}")
        logger.warning(f"Failed chunk IDs: {', '.join(failed_chunks[:5])}{'...' if len(failed_chunks) > 5 else ''}")
        logger.warning(f"Check workspace/logs/failed_chunks/ for error details")

    if total_stats['total_generated'] > 0:
        verification_rate = (total_stats['total_verified'] / total_stats['total_generated']) * 100
        logger.info(f"Verification rate: {verification_rate:.1f}%")

    logger.info("=" * 80)

    return total_stats


@click.command()
@click.option('--workspace', required=True, type=click.Path(exists=True), help='Workspace directory')
@click.option('--config', required=True, type=click.Path(exists=True), help='Config file path')
@click.option('--parallel', default=6, type=int, help='Number of concurrent chunk processors')
@click.option('--resume', is_flag=True, help='Skip already processed chunks')
@click.option('--verbose', is_flag=True, help='Enable debug logging')
def main(workspace: str, config: str, parallel: int, resume: bool, verbose: bool):
    """Generate synthetic examples from chunks and verify them."""

    # Load environment variables
    load_dotenv()

    # Load config
    cfg = load_config(config)

    # Setup logging
    log_level = "DEBUG" if verbose else cfg.audit.log_level
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(cfg.audit.log_dir) / f"script2_{timestamp}.log"
    setup_logger(__name__, log_file, log_level)

    logger.info("=" * 80)
    logger.info("Script 2: Generate & Verify")
    logger.info("=" * 80)
    logger.info(f"Workspace: {workspace}")
    logger.info(f"Config: {config}")
    logger.info(f"Parallelism: {parallel}")
    logger.info(f"Resume mode: {resume}")

    try:
        # Run async processing
        stats = asyncio.run(
            process_all_chunks(
                Path(workspace),
                cfg,
                parallel,
                resume
            )
        )

        # Exit with success
        if stats['total_chunks'] == 0:
            logger.warning("No chunks were processed")

    except Exception as e:
        logger.error(f"Generation and verification failed: {e}", exc_info=True)
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()

