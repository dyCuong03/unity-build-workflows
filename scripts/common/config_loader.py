"""
Configuration loading and merging library for Unity build pipeline.

Provides deterministic deep merge for layered BuildConfig JSON files.
Merge precedence: CLI arguments > environment config > base config > code defaults.
"""
import copy
import json
from pathlib import Path


def deep_merge(base, override):
    """Recursively merge override dict into base dict.

    - Dicts are merged recursively.
    - Lists in override replace lists in base (no concatenation).
    - Scalar values in override replace scalars in base.
    - Neither input is mutated; returns a new dict.

    Args:
        base: Base configuration dictionary.
        override: Override configuration dictionary.

    Returns:
        New merged dictionary.
    """
    if not isinstance(base, dict) or not isinstance(override, dict):
        return copy.deepcopy(override)

    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)

    return result


def load_config(config_dir, environment=None, cli_overrides=None):
    """Load and merge layered BuildConfig files.

    Loads base.json, then environment-specific JSON, then applies CLI overrides.

    Args:
        config_dir: Path to BuildConfig directory.
        environment: Environment name (e.g. "staging"). If provided, loads {environment}.json.
        cli_overrides: Dictionary of CLI-provided overrides.

    Returns:
        Merged configuration dictionary.

    Raises:
        FileNotFoundError: If base.json doesn't exist.
        json.JSONDecodeError: If JSON is malformed.
    """
    config_path = Path(config_dir)

    # Load base config
    base_file = config_path / "base.json"
    if not base_file.exists():
        raise FileNotFoundError(f"Base config not found: {base_file}")

    with open(base_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Load environment overlay
    if environment:
        env_file = config_path / f"{environment}.json"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                env_config = json.load(f)
            config = deep_merge(config, env_config)

    # Apply CLI overrides
    if cli_overrides:
        config = deep_merge(config, cli_overrides)

    return config
