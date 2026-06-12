#!/usr/bin/env python3
"""
prepare_ios_build.py
Prepare iOS signing environment:
- Import certificate and provisioning profile into keychain
- Set outputs for downstream Xcode steps
"""

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path


KEYCHAIN_NAME = "build.keychain"
KEYCHAIN_PASS = "build-keychain-temp-pass"
CERT_TEMP_PATH = "/tmp/apple-cert.p12"
PROFILE_TEMP_PATH = "/tmp/apple.mobileprovision"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"ERROR: Command failed: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def decode_b64_file(b64_data: str, output_path: str) -> None:
    """Decode base64 data and write to file."""
    try:
        data = base64.b64decode(b64_data)
    except Exception as e:
        print(f"ERROR: Failed to decode base64 data: {e}", file=sys.stderr)
        sys.exit(1)
    with open(output_path, "wb") as f:
        f.write(data)
    os.chmod(output_path, 0o600)


def setup_keychain(cert_path: str, cert_password: str) -> None:
    """Create a temporary keychain and import the certificate."""
    # Create keychain
    run(["security", "create-keychain", "-p", KEYCHAIN_PASS, KEYCHAIN_NAME])
    run(["security", "set-keychain-settings", "-lut", "21600", KEYCHAIN_NAME])
    run(["security", "unlock-keychain", "-p", KEYCHAIN_PASS, KEYCHAIN_NAME])

    # Add to keychain search list
    result = run(["security", "list-keychains", "-d", "user"], check=False)
    existing = result.stdout.strip().replace('"', "").split()
    run(["security", "list-keychains", "-d", "user", "-s", KEYCHAIN_NAME] + existing)

    # Import certificate
    run([
        "security", "import", cert_path,
        "-k", KEYCHAIN_NAME,
        "-P", cert_password,
        "-T", "/usr/bin/codesign",
        "-T", "/usr/bin/security",
    ])

    # Allow codesign to access without prompting
    run([
        "security", "set-key-partition-list",
        "-S", "apple-tool:,apple:",
        "-s", "-k", KEYCHAIN_PASS,
        KEYCHAIN_NAME,
    ])
    print("[prepare_ios] Certificate imported to keychain", file=sys.stderr)


def install_provisioning_profile(profile_path: str) -> str:
    """Install provisioning profile and return its UUID."""
    # Get UUID from profile
    result = run([
        "security", "cms", "-D", "-i", profile_path,
    ])
    # Parse plist output for UUID
    uuid = ""
    lines = result.stdout.split("\n")
    for i, line in enumerate(lines):
        if "<key>UUID</key>" in line and i + 1 < len(lines):
            uuid_line = lines[i + 1]
            import re
            match = re.search(r"<string>([^<]+)</string>", uuid_line)
            if match:
                uuid = match.group(1)
                break

    if not uuid:
        print("[prepare_ios] WARNING: Could not extract profile UUID", file=sys.stderr)
        uuid = "unknown"

    # Install profile
    profiles_dir = Path.home() / "Library" / "MobileDevice" / "Provisioning Profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    dest = profiles_dir / f"{uuid}.mobileprovision"
    import shutil
    shutil.copy2(profile_path, dest)
    print(f"[prepare_ios] Provisioning profile installed: {uuid}", file=sys.stderr)
    return uuid


def set_github_output(key: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{key}={value}\n")


def mask_secret(value: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") and value:
        print(f"::add-mask::{value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare iOS signing environment")
    parser.add_argument("--environment", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--config-path", default="BuildConfig")
    args = parser.parse_args()

    cert_b64 = os.environ.get("APPLE_CERT_BASE64", "")
    cert_password = os.environ.get("APPLE_CERT_PASSWORD", "")
    profile_b64 = os.environ.get("APPLE_PROV_PROFILE_BASE64", "")
    team_id = os.environ.get("APPLE_TEAM_ID", "")

    if not cert_b64:
        if args.environment == "development":
            print("[prepare_ios] No certificate — skipping signing for development", file=sys.stderr)
            set_github_output("signing-configured", "false")
            return
        print("ERROR: APPLE_CERT_BASE64 is required for non-development builds", file=sys.stderr)
        sys.exit(1)

    # Mask sensitive values
    if cert_password:
        mask_secret(cert_password)

    # Decode cert and profile
    decode_b64_file(cert_b64, CERT_TEMP_PATH)
    if profile_b64:
        decode_b64_file(profile_b64, PROFILE_TEMP_PATH)

    # Setup keychain
    setup_keychain(CERT_TEMP_PATH, cert_password)

    # Install provisioning profile
    profile_uuid = ""
    if profile_b64:
        profile_uuid = install_provisioning_profile(PROFILE_TEMP_PATH)

    set_github_output("signing-configured", "true")
    set_github_output("keychain-name", KEYCHAIN_NAME)
    set_github_output("profile-uuid", profile_uuid)
    set_github_output("team-id", team_id)

    print(
        f"[prepare_ios] iOS signing ready: team={team_id}, profile={profile_uuid}",
        file=sys.stderr,
    )

    # Write ExportOptions.plist template
    export_options = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>{"app-store" if args.environment == "production" else "development"}</string>
    <key>teamID</key>
    <string>{team_id}</string>
    <key>uploadBitcode</key>
    <false/>
    <key>compileBitcode</key>
    <false/>
    <key>uploadSymbols</key>
    <true/>
</dict>
</plist>
"""
    with open("/tmp/ExportOptions.plist", "w") as f:
        f.write(export_options)
    print("[prepare_ios] ExportOptions.plist written", file=sys.stderr)


if __name__ == "__main__":
    main()
