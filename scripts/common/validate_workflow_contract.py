#!/usr/bin/env python3
"""
validate_workflow_contract.py
Validate that a project's BuildConfig satisfies the workflow contract
(required inputs, expected structure, platform-specific constraints).
"""

import argparse
import json
import sys
from pathlib import Path

PLATFORM_CONTRACTS: dict[str, dict] = {
    "Android": {
        "required_secrets_hint": [
            "ANDROID_KEYSTORE_BASE64",
            "ANDROID_KEYSTORE_PASS",
            "ANDROID_KEY_ALIAS",
            "ANDROID_KEY_PASS",
        ],
        "required_config_fields": [
            "version",
            "package_name",
            "min_sdk_version",
            "target_sdk_version",
        ],
    },
    "iOS": {
        "required_secrets_hint": [
            "APPLE_CERT_BASE64",
            "APPLE_CERT_PASSWORD",
            "APPLE_PROV_PROFILE_BASE64",
            "APPLE_TEAM_ID",
            "APPLE_APP_ID",
        ],
        "required_config_fields": [
            "version",
            "bundle_id",
            "team_id",
        ],
    },
    "Windows64": {
        "required_secrets_hint": [],
        "required_config_fields": ["version", "product_name"],
    },
    "WebGL": {
        "required_secrets_hint": [],
        "required_config_fields": ["version", "product_name"],
    },
}


def load_configs(config_path: Path) -> dict:
    """Load and merge all JSON files in config directory."""
    merged = {}
    if config_path.is_file():
        with open(config_path) as f:
            return json.load(f)
    if config_path.is_dir():
        for json_file in sorted(config_path.glob("*.json")):
            try:
                with open(json_file) as f:
                    merged.update(json.load(f))
            except (json.JSONDecodeError, IOError) as e:
                print(f"WARNING: Could not parse {json_file}: {e}", file=sys.stderr)
    return merged


def validate_contract(
    config: dict,
    platform: str,
) -> tuple[list[str], list[str]]:
    """
    Returns (errors, warnings) based on workflow contract.
    """
    errors: list[str] = []
    warnings: list[str] = []

    contract = PLATFORM_CONTRACTS.get(platform)
    if not contract:
        warnings.append(f"Unknown platform '{platform}' — no contract defined")
        return errors, warnings

    # Check required config fields
    for field in contract["required_config_fields"]:
        if field not in config:
            errors.append(f"Workflow contract violation: missing required config field '{field}' for {platform}")

    # Warn about required secrets (cannot verify at config-read time)
    if contract["required_secrets_hint"]:
        warnings.append(
            f"Ensure the following GitHub secrets are configured for {platform}: "
            + ", ".join(contract["required_secrets_hint"])
        )

    # Check Unity version compatibility hint
    unity_version = config.get("unity_version", "")
    if unity_version:
        parts = unity_version.split(".")
        try:
            year = int(parts[0])
            if year < 2021:
                warnings.append(
                    f"Unity {unity_version} may not support all workflow features. "
                    "Recommend Unity 2021 LTS or newer."
                )
        except (ValueError, IndexError):
            warnings.append(f"unity_version '{unity_version}' does not look like a valid Unity version")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Unity workflow contract")
    parser.add_argument("--config-path", required=True, help="BuildConfig directory or file")
    parser.add_argument("--platform", required=True, help="Target platform")
    parser.add_argument("--output", default="", help="Write warnings to this file")
    args = parser.parse_args()

    config_path = Path(args.config_path)
    try:
        config = load_configs(config_path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Could not load config: {e}", file=sys.stderr)
        sys.exit(1)

    errors, warnings = validate_contract(config, args.platform)

    output_lines = []
    if errors:
        for e in errors:
            line = f"ERROR: {e}"
            print(line, file=sys.stderr)
            output_lines.append(line)
    if warnings:
        for w in warnings:
            line = f"WARNING: {w}"
            print(line, file=sys.stderr)
            output_lines.append(line)

    if not errors and not warnings:
        print(f"OK: Workflow contract satisfied for {args.platform}")

    if args.output and output_lines:
        Path(args.output).write_text("\n".join(output_lines) + "\n")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
