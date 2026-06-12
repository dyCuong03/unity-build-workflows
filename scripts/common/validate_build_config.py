#!/usr/bin/env python3
"""
validate_build_config.py
Validate BuildConfig JSON files against schema and semantic rules.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Minimal JSON schema validator (no external deps required)
REQUIRED_FIELDS_BASE = {"version", "bundle_id"}
REQUIRED_FIELDS_PER_PLATFORM: dict[str, set[str]] = {
    "Android": {"package_name", "min_sdk_version", "target_sdk_version"},
    "iOS": {"bundle_id", "team_id"},
    "Windows64": {"product_name"},
    "WebGL": {"product_name"},
}
DEV_FLAGS = ["development_build", "allow_debugging", "enable_deep_profiling", "connect_to_host"]
SEMVER_RE = __import__("re").compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")
KNOWN_ENVIRONMENTS = {"development", "staging", "production"}


def load_config(config_path: Path) -> dict[str, Any]:
    """Load all JSON files from a BuildConfig directory and merge them."""
    merged: dict[str, Any] = {}
    if not config_path.is_dir():
        # Single file
        if config_path.is_file():
            with open(config_path) as f:
                return json.load(f)
        raise FileNotFoundError(f"Config path not found: {config_path}")

    for filename in sorted(config_path.glob("*.json")):
        try:
            with open(filename) as f:
                data = json.load(f)
            merged.update(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {filename}: {e}") from e

    return merged


def validate(
    config: dict[str, Any],
    platform: str,
    environment: str = "development",
    check_release_flags: bool = False,
    strict: bool = False,
) -> tuple[list[str], list[str]]:
    """
    Validate config. Returns (errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check required base fields
    for field in REQUIRED_FIELDS_BASE:
        if field not in config:
            errors.append(f"Missing required field: '{field}'")

    # Version format
    version = config.get("version", "")
    if version and not SEMVER_RE.match(str(version)):
        errors.append(f"Version '{version}' does not match semver format (expected X.Y.Z)")

    # Platform-specific required fields
    platform_reqs = REQUIRED_FIELDS_PER_PLATFORM.get(platform, set())
    for field in platform_reqs:
        if field not in config:
            errors.append(f"Missing required field for {platform}: '{field}'")

    # Environment
    env = config.get("environment", environment)
    if env not in KNOWN_ENVIRONMENTS:
        warnings.append(f"Unknown environment: '{env}' (expected: {', '.join(KNOWN_ENVIRONMENTS)})")

    # Release flag checks
    if check_release_flags or environment == "production":
        for flag in DEV_FLAGS:
            if config.get(flag) is True:
                msg = f"Dev flag '{flag}' is enabled — must be disabled for production"
                if check_release_flags or strict:
                    errors.append(msg)
                else:
                    warnings.append(msg)

    # Android-specific
    if platform == "Android":
        min_sdk = config.get("min_sdk_version")
        target_sdk = config.get("target_sdk_version")
        if min_sdk is not None and target_sdk is not None:
            if int(min_sdk) > int(target_sdk):
                errors.append(
                    f"min_sdk_version ({min_sdk}) cannot be greater than target_sdk_version ({target_sdk})"
                )
        if min_sdk is not None and int(min_sdk) < 21:
            warnings.append(f"min_sdk_version {min_sdk} is below Android 5.0 (API 21)")

    # iOS-specific
    if platform == "iOS":
        min_ios = config.get("min_ios_version", "")
        if min_ios:
            parts = str(min_ios).split(".")
            try:
                major = int(parts[0])
                if major < 12:
                    warnings.append(f"min_ios_version {min_ios} is below iOS 12 — may not pass App Store review")
            except ValueError:
                errors.append(f"min_ios_version '{min_ios}' is not a valid version number")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Unity BuildConfig JSON")
    parser.add_argument("--config-path", required=True, help="BuildConfig directory or file")
    parser.add_argument("--platform", required=True, help="Target platform")
    parser.add_argument("--environment", default="development", help="Build environment")
    parser.add_argument(
        "--check-release-flags",
        action="store_true",
        help="Fail if any dev flags are enabled",
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Output results as JSON (for machine consumption)",
    )
    args = parser.parse_args()

    config_path = Path(args.config_path)
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as e:
        if args.output_json:
            print(json.dumps({"error": str(e), "error_count": 1, "warning_count": 0}))
        else:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    errors, warnings = validate(
        config,
        platform=args.platform,
        environment=args.environment,
        check_release_flags=args.check_release_flags,
        strict=args.strict,
    )

    if args.strict:
        errors.extend(warnings)
        warnings = []

    result = {
        "config_path": str(config_path),
        "platform": args.platform,
        "environment": args.environment,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "valid": len(errors) == 0,
    }

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
        if warnings:
            for w in warnings:
                print(f"WARNING: {w}", file=sys.stderr)
        if not errors and not warnings:
            print(f"OK: BuildConfig valid for {args.platform} ({args.environment})")

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
