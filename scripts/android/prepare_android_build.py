#!/usr/bin/env python3
"""
prepare_android_build.py
Prepare Android signing environment:
- Decode base64 keystore to temp file
- Write signing config for Unity build
- Set output env vars for downstream steps
"""

import argparse
import base64
import json
import os
import sys
import tempfile
from pathlib import Path


KEYSTORE_TEMP_PATH = "/tmp/android-keystore.jks"


def decode_keystore(keystore_b64: str) -> str:
    """Decode base64 keystore and write to temp file. Returns path."""
    try:
        keystore_bytes = base64.b64decode(keystore_b64)
    except Exception as e:
        print(f"ERROR: Failed to decode keystore base64: {e}", file=sys.stderr)
        sys.exit(1)

    with open(KEYSTORE_TEMP_PATH, "wb") as f:
        f.write(keystore_bytes)
    os.chmod(KEYSTORE_TEMP_PATH, 0o600)
    print(f"[prepare_android] Keystore written to: {KEYSTORE_TEMP_PATH}", file=sys.stderr)
    return KEYSTORE_TEMP_PATH


def write_signing_config(
    keystore_path: str,
    keystore_pass: str,
    key_alias: str,
    key_pass: str,
    output_path: str,
) -> None:
    """Write a JSON signing config for Unity build scripts."""
    config = {
        "keystore_path": keystore_path,
        "key_alias": key_alias,
        # Passwords are written here for local Unity editor pickup only
        # They will be masked by GitHub Actions secret masking
        "keystore_pass": keystore_pass,
        "key_pass": key_pass,
    }
    with open(output_path, "w") as f:
        json.dump(config, f)
    os.chmod(output_path, 0o600)
    print(f"[prepare_android] Signing config written to: {output_path}", file=sys.stderr)


def set_github_output(key: str, value: str) -> None:
    """Write a GitHub Actions output variable."""
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{key}={value}\n")
    else:
        print(f"  {key}={value}")


def mask_secret(value: str) -> None:
    """Mask a value in GitHub Actions logs."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Android signing environment")
    parser.add_argument("--environment", required=True, help="Build environment")
    parser.add_argument("--version", required=True, help="Build version")
    parser.add_argument("--config-path", default="BuildConfig", help="BuildConfig directory")
    args = parser.parse_args()

    # Read secrets from environment (never from args — avoid shell history exposure)
    keystore_b64 = os.environ.get("ANDROID_KEYSTORE_BASE64", "")
    keystore_pass = os.environ.get("ANDROID_KEYSTORE_PASS", "")
    key_alias = os.environ.get("ANDROID_KEY_ALIAS", "")
    key_pass = os.environ.get("ANDROID_KEY_PASS", "")

    if not keystore_b64:
        if args.environment == "development":
            print(
                "[prepare_android] No keystore provided — skipping signing setup for development",
                file=sys.stderr,
            )
            set_github_output("keystore-configured", "false")
            return
        else:
            print(
                "ERROR: ANDROID_KEYSTORE_BASE64 is required for non-development builds",
                file=sys.stderr,
            )
            sys.exit(1)

    # Mask sensitive values in logs
    if keystore_pass:
        mask_secret(keystore_pass)
    if key_pass:
        mask_secret(key_pass)

    # Decode and write keystore
    keystore_path = decode_keystore(keystore_b64)

    # Write signing config
    signing_config_path = "/tmp/signing-config.json"
    write_signing_config(keystore_path, keystore_pass, key_alias, key_pass, signing_config_path)

    # Set outputs
    set_github_output("keystore-path", keystore_path)
    set_github_output("signing-config-path", signing_config_path)
    set_github_output("keystore-configured", "true")

    print(
        f"[prepare_android] Android signing prepared for {args.environment} v{args.version}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
