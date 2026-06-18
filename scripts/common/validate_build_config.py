#!/usr/bin/env python3
"""
validate_build_config.py
Validate BuildConfig JSON files against schema and semantic rules.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Base fields expected in every BuildConfig (camelCase per current schema).
# bundle_id/team_id are platform-specific and live inside 'ios'/'android' blocks.
REQUIRED_FIELDS_BASE = {"bundleVersion"}
REQUIRED_FIELDS_PER_PLATFORM: dict[str, set[str]] = {
    # Android block fields validated by the 'android' sub-block; no top-level requirements.
    "Android": set(),
    # iOS block validated by _validate_ios_block(); bundleIdentifier + signing checked there.
    "iOS": set(),
    "Windows64": set(),
    "WebGL": set(),
}
DEV_FLAGS = ["development_build", "allow_debugging", "enable_deep_profiling", "connect_to_host"]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")
KNOWN_ENVIRONMENTS = {"development", "staging", "production"}

# ── iOS 'ios' block validation ─────────────────────────────────────────────

_IOS_BUNDLE_ID_RE = re.compile(
    r"^[a-zA-Z][a-zA-Z0-9_\-]*(\.[a-zA-Z][a-zA-Z0-9_\-]*){1,}$"
)
_IOS_VERSION_RE = re.compile(r"^\d+\.\d+$")
_IOS_MIN_TARGET = (14, 0)
_IOS_SUPPORTED_ARCHITECTURES = frozenset({"ARM64", "Universal"})
# "app-store" kept for backward compat; "app-store-connect" is the canonical new name
_IOS_SUPPORTED_EXPORT_METHODS = frozenset({
    "app-store", "app-store-connect", "ad-hoc", "development", "enterprise",
})
_IOS_SUPPORTED_SIGNING_STYLES = frozenset({"manual", "automatic"})


def _validate_ios_block(
    ios: dict,
    errors: list,
    warnings: list,
) -> None:
    """
    Validate the camelCase fields inside the 'ios' BuildConfig block.

    Called when platform == 'iOS' and the top-level config contains an 'ios' key.
    No secrets are validated here — they live in GitHub secrets only.
    """
    # ── bundleIdentifier ───────────────────────────────────────────────────
    bundle_id = ios.get("bundleIdentifier", "")
    if not bundle_id:
        errors.append(
            "Missing required field in ios block: 'bundleIdentifier' "
            "(e.g. com.company.game)."
        )
    elif not _IOS_BUNDLE_ID_RE.match(bundle_id):
        errors.append(
            f"ios.bundleIdentifier '{bundle_id}' is not a valid reverse-DNS identifier. "
            "Expected at least two dot-separated components starting with a letter."
        )

    # ── buildNumber ────────────────────────────────────────────────────────
    build_number = ios.get("buildNumber")
    if build_number is not None and not re.match(r"^\d+$", str(build_number)):
        errors.append(
            f"ios.buildNumber '{build_number}' must be a numeric string (e.g. '42')."
        )

    # ── marketingVersion ───────────────────────────────────────────────────
    marketing_version = ios.get("marketingVersion")
    if marketing_version is not None:
        if not re.match(r"^\d+\.\d+\.\d+$", str(marketing_version)):
            errors.append(
                f"ios.marketingVersion '{marketing_version}' must follow semver "
                "MAJOR.MINOR.PATCH format (e.g. '1.2.3')."
            )

    # ── targetOSVersion ────────────────────────────────────────────────────
    target_os = ios.get("targetOSVersion", "14.0")
    if not _IOS_VERSION_RE.match(str(target_os)):
        errors.append(
            f"ios.targetOSVersion '{target_os}' must be in MAJOR.MINOR format (e.g. '14.0')."
        )
    else:
        try:
            parts = str(target_os).split(".")
            major, minor = int(parts[0]), int(parts[1])
            if (major, minor) < _IOS_MIN_TARGET:
                errors.append(
                    f"ios.targetOSVersion '{target_os}' is below the minimum supported "
                    f"deployment target {'.'.join(str(v) for v in _IOS_MIN_TARGET)}."
                )
        except (ValueError, IndexError):
            errors.append(
                f"ios.targetOSVersion '{target_os}' could not be parsed."
            )

    # ── architecture ───────────────────────────────────────────────────────
    architecture = ios.get("architecture")
    if architecture is not None and architecture not in _IOS_SUPPORTED_ARCHITECTURES:
        errors.append(
            f"ios.architecture '{architecture}' is not supported. "
            f"Supported values: {', '.join(sorted(_IOS_SUPPORTED_ARCHITECTURES))}."
        )

    # ── exportMethod ───────────────────────────────────────────────────────
    export_method = ios.get("exportMethod", "app-store")
    if export_method not in _IOS_SUPPORTED_EXPORT_METHODS:
        errors.append(
            f"ios.exportMethod '{export_method}' is not supported. "
            f"Supported values: {', '.join(sorted(_IOS_SUPPORTED_EXPORT_METHODS))}."
        )

    # ── signingStyle / automaticSigning ────────────────────────────────────
    # New: signingStyle (string enum).  Legacy: automaticSigning (boolean).
    if "signingStyle" in ios:
        signing_style = ios["signingStyle"]
        if signing_style not in _IOS_SUPPORTED_SIGNING_STYLES:
            errors.append(
                f"ios.signingStyle '{signing_style}' is not valid. "
                f"Supported values: {', '.join(sorted(_IOS_SUPPORTED_SIGNING_STYLES))}."
            )
    elif "automaticSigning" in ios:
        signing_style = "automatic" if ios["automaticSigning"] else "manual"
    else:
        signing_style = "manual"  # schema default

    if signing_style == "manual":
        if not ios.get("provisioningProfileSpecifier"):
            errors.append(
                "ios signingStyle is 'manual' but ios.provisioningProfileSpecifier is missing."
            )
        if not ios.get("codeSignIdentity"):
            errors.append(
                "ios signingStyle is 'manual' but ios.codeSignIdentity is missing."
            )

    # ── uploadToTestFlight advisory ────────────────────────────────────────
    if ios.get("uploadToTestFlight") is True:
        warnings.append(
            "ios.uploadToTestFlight is true — this is a request flag only. "
            "The actual TestFlight upload requires App Store Connect secrets configured "
            "in the workflow."
        )

    # ── enableBitcode advisory ─────────────────────────────────────────────
    if ios.get("enableBitcode") is True:
        warnings.append(
            "ios.enableBitcode is true. Bitcode was deprecated in Xcode 14+. "
            "Set to false for modern toolchains."
        )


def load_config(config_path: Path) -> dict[str, Any]:
    """Load all JSON files from a BuildConfig directory and merge them.

    Raises:
        FileNotFoundError: with actionable message when the path does not exist.
        ValueError: with file path + line/column context when JSON is malformed.
    """
    merged: dict[str, Any] = {}
    if not config_path.is_dir():
        # Single file
        if config_path.is_file():
            with open(config_path) as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON in {config_path} "
                        f"at line {exc.lineno}, column {exc.colno}: {exc.msg}. "
                        "Open the file, go to the reported line/column, and fix the syntax error."
                    ) from exc
        raise FileNotFoundError(
            f"Config path not found: {config_path}. "
            "Pass --config-path pointing to a BuildConfig directory or a single JSON file."
        )

    json_files = sorted(config_path.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(
            f"No JSON files found in BuildConfig directory: {config_path}. "
            "Add at least one *.json file with the required fields."
        )

    for filename in json_files:
        try:
            with open(filename) as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in {filename} "
                f"at line {exc.lineno}, column {exc.colno}: {exc.msg}. "
                "Open the file, go to the reported line/column, and fix the syntax error."
            ) from exc
        if not isinstance(data, dict):
            raise ValueError(
                f"Expected a JSON object (dict) in {filename}, "
                f"got {type(data).__name__}. "
                "Each BuildConfig file must be a top-level JSON object."
            )
        merged.update(data)

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
            errors.append(
                f"Missing required field: '{field}'. "
                "Add this field to your base.json BuildConfig file."
            )

    # Version format
    version = config.get("version", "")
    if version and not SEMVER_RE.match(str(version)):
        errors.append(f"Version '{version}' does not match semver format (expected X.Y.Z)")

    # Platform-specific required fields
    platform_reqs = REQUIRED_FIELDS_PER_PLATFORM.get(platform, set())
    for field in platform_reqs:
        if field not in config:
            errors.append(
                f"Missing required field for platform '{platform}': '{field}'. "
                f"Add '{field}' to your BuildConfig for {platform} builds."
            )

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
        # Legacy top-level min_ios_version check (kept for backward compat)
        min_ios = config.get("min_ios_version", "")
        if min_ios:
            parts = str(min_ios).split(".")
            try:
                major = int(parts[0])
                if major < 12:
                    warnings.append(f"min_ios_version {min_ios} is below iOS 12 — may not pass App Store review")
            except ValueError:
                errors.append(f"min_ios_version '{min_ios}' is not a valid version number")

        # Validate the iOS block — 'iOS' is canonical, 'ios' is legacy fallback.
        ios_block = config.get("iOS") or config.get("ios")
        used_key = "iOS" if "iOS" in config else ("ios" if "ios" in config else None)
        if ios_block is not None:
            if isinstance(ios_block, dict):
                if used_key == "ios":
                    warnings.append(
                        "BuildConfig uses legacy 'ios' key — migrate to canonical 'iOS'."
                    )
                _validate_ios_block(ios_block, errors, warnings)
            else:
                errors.append(f"'{used_key}' key in BuildConfig must be an object.")

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
            print(json.dumps({
                "config_path": str(config_path),
                "error": str(e),
                "error_count": 1,
                "warning_count": 0,
                "errors": [str(e)],
                "warnings": [],
                "valid": False,
            }))
        else:
            print(f"ERROR [{config_path}]: {e}", file=sys.stderr)
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
                # Prefix each error with the config path so CI logs are immediately
                # actionable — operator can open the file without hunting for context.
                print(f"ERROR [{config_path}]: {e}", file=sys.stderr)
        if warnings:
            for w in warnings:
                print(f"WARNING [{config_path}]: {w}", file=sys.stderr)
        if not errors and not warnings:
            print(f"OK: BuildConfig valid for {args.platform} ({args.environment})")

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
