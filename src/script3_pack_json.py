"""Script 3: Pack verified items into sharded train/test datasets.
python -m src.script3_pack_json --workspace ./workspace --output ./output --config ./config/app.config.yaml --seed 42
"""

import json
import random
import time
import click
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from .common.config import load_config, Config
from .common.ids import generate_run_id
from .common.io_utils import JSONLWriter, JSONLReader, ensure_dir, find_files, setup_logger
from .common.validation import validate_generated_item, validate_shard_manifest

logger = logging.getLogger(__name__)


class DatasetPacker:
    """Pack verified items into sharded datasets."""
    
    def __init__(self, config: Config):
        """
        Initialize dataset packer.
        
        Args:
            config: Configuration object
        """
        self.config = config
        
        logger.info(
            f"DatasetPacker initialized: "
            f"splits={list(config.packing.splits.keys())}, "
            f"shard_size={config.packing.shard_size}"
        )
    
    def collect_verified_items(self, workspace: Path) -> list[dict]:
        """
        Find and read all verified items from workspace.
        
        Args:
            workspace: Workspace directory
            
        Returns:
            List of verified items
        """
        logger.info("Collecting verified items...")
        
        verified_dir = workspace / "verified"
        
        if not verified_dir.exists():
            logger.warning(f"Verified directory not found: {verified_dir}")
            return []
        
        # Find all verified JSONL files
        verified_files = find_files(verified_dir, "**/*.verified.jsonl")
        
        if not verified_files:
            logger.warning(f"No verified files found in {verified_dir}")
            return []
        
        logger.info(f"Found {len(verified_files)} verified files")
        
        # Collect all items
        all_items = []
        invalid_count = 0
        
        for verified_file in verified_files:
            try:
                with JSONLReader(verified_file) as reader:
                    for item in reader.read_lines():
                        # Validate item
                        is_valid, errors = validate_generated_item(item)
                        
                        if is_valid:
                            all_items.append(item)
                        else:
                            invalid_count += 1
                            logger.warning(
                                f"Invalid item in {verified_file}: {errors[:100]}"
                            )
            
            except Exception as e:
                logger.error(f"Error reading {verified_file}: {e}")
                continue
        
        logger.info(
            f"Collected {len(all_items)} valid items "
            f"({invalid_count} invalid items skipped)"
        )
        
        return all_items
    
    def shuffle_items(
        self,
        items: list[dict],
        seed: Optional[int] = None
    ) -> tuple[list[dict], int]:
        """
        Shuffle items with deterministic seed.
        
        Args:
            items: List of items
            seed: Random seed (defaults to timestamp-based)
            
        Returns:
            Tuple of (shuffled items, seed used)
        """
        if seed is None:
            seed = int(time.time())
        
        logger.info(f"Shuffling {len(items)} items with seed={seed}")
        
        items_copy = items.copy()
        random.Random(seed).shuffle(items_copy)
        
        return items_copy, seed
    
    def split_items(
        self,
        items: list[dict],
        ratios: dict[str, float]
    ) -> dict[str, list[dict]]:
        """
        Split items into train/test/val sets.
        
        Args:
            items: Shuffled list of items
            ratios: Dict like {"train": 0.98, "test": 0.02}
            
        Returns:
            Dict of split_name -> items
        """
        total = len(items)
        splits = {}
        start = 0
        
        logger.info(f"Splitting {total} items with ratios: {ratios}")
        
        # Validate ratios sum to ~1.0
        ratio_sum = sum(ratios.values())
        if not (0.99 <= ratio_sum <= 1.01):
            logger.warning(
                f"Split ratios sum to {ratio_sum:.3f}, expected ~1.0. "
                f"Normalizing ratios."
            )
            # Normalize ratios
            ratios = {k: v / ratio_sum for k, v in ratios.items()}
        
        # Split items
        for split_name, ratio in ratios.items():
            count = int(total * ratio)
            end = start + count
            
            # Handle last split to include any remaining items
            if split_name == list(ratios.keys())[-1]:
                end = total
            
            splits[split_name] = items[start:end]
            start = end
            
            logger.info(f"Split '{split_name}': {len(splits[split_name])} items ({ratio*100:.1f}%)")
        
        return splits
    
    def write_shards(
        self,
        split_name: str,
        items: list[dict],
        output_dir: Path,
        shard_size: int
    ) -> list[dict]:
        """
        Write items to sharded JSONL files.
        
        Args:
            split_name: Name of split (e.g., "train")
            items: List of items for this split
            output_dir: Output directory for shards
            shard_size: Items per shard
            
        Returns:
            List of shard metadata dicts
        """
        if not items:
            logger.warning(f"No items to write for split '{split_name}'")
            return []
        
        logger.info(f"Writing {len(items)} items for split '{split_name}' (shard_size={shard_size})")
        
        shard_metadata = []
        num_shards = (len(items) + shard_size - 1) // shard_size
        
        # Ensure output directory exists
        ensure_dir(output_dir)
        
        for shard_idx in range(num_shards):
            start = shard_idx * shard_size
            end = min(start + shard_size, len(items))
            shard_items = items[start:end]
            
            shard_file = output_dir / f"{split_name}-{shard_idx:05d}.jsonl"
            
            with JSONLWriter(shard_file) as writer:
                for item in shard_items:
                    writer.write_line(item)
            
            shard_metadata.append({
                "file": shard_file.name,
                "num_items": len(shard_items)
            })
            
            logger.debug(f"Wrote {shard_file.name}: {len(shard_items)} items")
        
        logger.info(f"Split '{split_name}': wrote {num_shards} shards")
        
        return shard_metadata
    
    def create_manifest(
        self,
        run_id: str,
        splits_metadata: dict,
        seed: int
    ) -> dict:
        """
        Create manifest following schemas/shard_manifest.schema.json.
        
        Args:
            run_id: Run ID
            splits_metadata: Metadata for each split
            seed: Random seed used for shuffling
            
        Returns:
            Manifest dictionary
        """
        total_items = sum(
            meta["num_items"]
            for meta in splits_metadata.values()
        )
        
        manifest = {
            "run_id": run_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "total_items": total_items,
            "shuffle_seed": seed,
            "splits": {}
        }
        
        for split_name, meta in splits_metadata.items():
            manifest["splits"][split_name] = {
                "num_items": meta["num_items"],
                "shards": meta["shards"]
            }
        
        # Validate manifest
        is_valid, errors = validate_shard_manifest(manifest)
        if not is_valid:
            logger.warning(f"Manifest validation failed: {errors}")
        
        return manifest
    
    def create_dataset_info(
        self,
        splits_metadata: dict,
        run_id: str,
        seed: int
    ) -> dict:
        """
        Create dataset_info.json with summary statistics.
        
        Args:
            splits_metadata: Metadata for each split
            run_id: Run ID
            seed: Random seed used
            
        Returns:
            Dataset info dictionary
        """
        total_items = sum(
            meta["num_items"]
            for meta in splits_metadata.values()
        )
        
        dataset_info = {
            "run_id": run_id,
            "total_items": total_items,
            "shuffle_seed": seed,
            "splits": {},
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        
        for split_name, meta in splits_metadata.items():
            dataset_info["splits"][split_name] = {
                "num_items": meta["num_items"],
                "num_shards": meta["num_shards"]
            }
        
        return dataset_info


def pack_dataset(
    workspace: Path,
    output: Path,
    config: Config,
    seed: Optional[int] = None
) -> dict:
    """
    Orchestrate the full packing process.

    Args:
        workspace: Workspace directory
        output: Output directory
        config: Configuration object
        seed: Random seed for shuffling (optional)

    Returns:
        Statistics dictionary
    """
    logger.info("=" * 80)
    logger.info("Starting dataset packing...")
    logger.info("=" * 80)

    # Initialize packer
    packer = DatasetPacker(config)

    # Generate run ID
    run_id = generate_run_id()
    logger.info(f"Run ID: {run_id}")

    # Step 1: Collect verified items
    logger.info("Step 1: Collecting verified items...")
    items = packer.collect_verified_items(workspace)

    if not items:
        logger.error("No verified items found. Cannot create dataset.")
        return {
            "run_id": run_id,
            "total_items": 0,
            "splits": {}
        }

    logger.info(f"Collected {len(items)} verified items")

    # Step 2: Shuffle items
    logger.info("Step 2: Shuffling items...")
    shuffled_items, actual_seed = packer.shuffle_items(items, seed)
    logger.info(f"Shuffled with seed: {actual_seed}")

    # Step 3: Split items
    logger.info("Step 3: Splitting items...")
    splits = packer.split_items(shuffled_items, config.packing.splits)

    # Step 4: Write shards for each split
    logger.info("Step 4: Writing shards...")
    shards_dir = output / "shards"
    ensure_dir(shards_dir)

    splits_metadata = {}

    for split_name, split_items in splits.items():
        logger.info(f"Processing split '{split_name}'...")

        shard_metadata = packer.write_shards(
            split_name=split_name,
            items=split_items,
            output_dir=shards_dir,
            shard_size=config.packing.shard_size
        )

        splits_metadata[split_name] = {
            "num_items": len(split_items),
            "num_shards": len(shard_metadata),
            "shards": shard_metadata
        }

    # Step 5: Create dataset_info.json
    logger.info("Step 5: Creating dataset_info.json...")
    dataset_info = packer.create_dataset_info(splits_metadata, run_id, actual_seed)

    dataset_info_file = output / "dataset_info.json"
    with open(dataset_info_file, 'w', encoding='utf-8') as f:
        json.dump(dataset_info, f, indent=2, ensure_ascii=False)

    logger.info(f"Wrote {dataset_info_file}")

    # Step 6: Create manifest.json (if enabled)
    if config.audit.save_manifest:
        logger.info("Step 6: Creating manifest.json...")
        manifest = packer.create_manifest(run_id, splits_metadata, actual_seed)

        manifest_file = output / "manifest.json"
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        logger.info(f"Wrote {manifest_file}")
    else:
        logger.info("Step 6: Skipping manifest.json (disabled in config)")

    # Log final statistics
    logger.info("=" * 80)
    logger.info("Packing Complete")
    logger.info("=" * 80)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Total items: {len(items)}")
    logger.info(f"Shuffle seed: {actual_seed}")

    for split_name, meta in splits_metadata.items():
        logger.info(
            f"Split '{split_name}': {meta['num_items']} items, "
            f"{meta['num_shards']} shards"
        )

    logger.info(f"Output directory: {output}")
    logger.info("=" * 80)

    return {
        "run_id": run_id,
        "total_items": len(items),
        "shuffle_seed": actual_seed,
        "splits": splits_metadata
    }


@click.command()
@click.option('--workspace', required=True, type=click.Path(exists=True), help='Workspace directory')
@click.option('--output', required=True, type=click.Path(), help='Output directory')
@click.option('--config', required=True, type=click.Path(exists=True), help='Config file path')
@click.option('--seed', type=int, default=None, help='Random seed for shuffling (optional)')
@click.option('--verbose', is_flag=True, help='Enable debug logging')
def main(workspace: str, output: str, config: str, seed: Optional[int], verbose: bool):
    """Pack verified items into sharded train/test datasets."""

    # Load config
    cfg = load_config(config)

    # Setup logging
    log_level = "DEBUG" if verbose else cfg.audit.log_level
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(cfg.audit.log_dir) / f"script3_{timestamp}.log"
    setup_logger(__name__, log_file, log_level)

    logger.info("=" * 80)
    logger.info("Script 3: Pack & Shard Dataset")
    logger.info("=" * 80)
    logger.info(f"Workspace: {workspace}")
    logger.info(f"Output: {output}")
    logger.info(f"Config: {config}")
    logger.info(f"Seed: {seed if seed is not None else 'auto (timestamp-based)'}")

    try:
        # Pack dataset
        stats = pack_dataset(
            Path(workspace),
            Path(output),
            cfg,
            seed
        )

        # Exit with success
        if stats['total_items'] == 0:
            logger.warning("No items were packed")
        else:
            logger.info(f"Successfully packed {stats['total_items']} items")

    except Exception as e:
        logger.error(f"Packing failed: {e}", exc_info=True)
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()

