#!/usr/bin/env python3
"""
resolve_project_version.py
Resolve the Unity project build version from multiple sources:
  1. Git tag (if ref is a tag v*)
  2. BuildConfig JSON
  3. ProjectSettings/ProjectVersion.txt
  4. Environment variable UNITY_BUILD_VERSION
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def git_tag_version(ref: str) -> str | None:
    """Extract semver from a git tag ref (refs/tags/v1.2.3)."""
    if not ref:
        return None
    match = re.match(r"^refs/tags/v(.+)$", ref)
    if match:
        return match.group(1)
    # Also handle bare tag names
    match = re.match(r"^v(.+)$", ref)
    if match:
        return match.group(1)
    return None


def read_build_config(config_path: str, field: str = "version") -> str | None:
    """Read version (or another field) from BuildConfig JSON files."""
    config_dir = Path(config_path)
    # Try common config file names
    for filename in ["BuildConfig.json", "build_config.json", "config.json", "settings.json"]:
        config_file = config_dir / filename
        if config_file.is_file():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                value = data.get(field) or data.get("build", {}).get(field)
                if value:
                    return str(value)
            except (json.JSONDecodeError, IOError):
                continue

    # Try environment-specific config
    for env_name in ["production", "staging", "development"]:
        env_file = config_dir / f"{env_name}.json"
        if env_file.is_file():
            try:
                with open(env_file) as f:
                    data = json.load(f)
                value = data.get(field) or data.get("build", {}).get(field)
                if value:
                    return str(value)
            except (json.JSONDecodeError, IOError):
                continue

    return None


def read_project_settings_version(project_path: str) -> str | None:
    """Read version from Unity ProjectSettings/ProjectVersion.txt."""
    version_file = Path(project_path) / "ProjectSettings" / "ProjectVersion.txt"
    if not version_file.is_file():
        return None
    try:
        with open(version_file) as f:
            for line in f:
                if line.startswith("m_EditorVersion:"):
                    # This is Unity editor version, not game version
                    pass
        # Try ProjectSettings.asset for bundleVersion
        asset_file = Path(project_path) / "ProjectSettings" / "ProjectSettings.asset"
        if asset_file.is_file():
            with open(asset_file) as f:
                for line in f:
                    match = re.search(r"bundleVersion:\s*(.+)", line)
                    if match:
                        return match.group(1).strip()
    except IOError:
        pass
    return None


def get_git_describe(project_path: str) -> str | None:
    """Try git describe to get a pseudo-version from tags."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            raw = result.stdout.strip()
            # If it looks like v1.2.3-5-gabcdef, normalise
            match = re.match(r"^v?(\d+\.\d+\.\d+)", raw)
            if match:
                return match.group(1)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve Unity build version")
    parser.add_argument("--project-path", default=".", help="Unity project root")
    parser.add_argument("--config-path", default="BuildConfig", help="BuildConfig directory")
    parser.add_argument("--environment", default="development", help="Build environment")
    parser.add_argument("--ref", default="", help="Git ref (e.g. refs/tags/v1.2.3)")
    parser.add_argument(
        "--output-field",
        default="version",
        help="Field to read from config (default: version)",
    )
    args = parser.parse_args()

    version: str | None = None

    # Priority 1: env var override
    env_version = os.environ.get("UNITY_BUILD_VERSION")
    if env_version:
        version = env_version
        print(f"[resolve_version] Using env var UNITY_BUILD_VERSION: {version}", file=sys.stderr)

    # Priority 2: git tag
    if not version:
        version = git_tag_version(args.ref)
        if version:
            print(f"[resolve_version] Using git tag version: {version}", file=sys.stderr)

    # Priority 3: BuildConfig
    if not version:
        version = read_build_config(args.config_path, args.output_field)
        if version:
            print(f"[resolve_version] Using BuildConfig version: {version}", file=sys.stderr)

    # Priority 4: ProjectSettings
    if not version:
        version = read_project_settings_version(args.project_path)
        if version:
            print(f"[resolve_version] Using ProjectSettings version: {version}", file=sys.stderr)

    # Priority 5: git describe
    if not version:
        version = get_git_describe(args.project_path)
        if version:
            print(f"[resolve_version] Using git describe version: {version}", file=sys.stderr)

    # Fallback
    if not version:
        version = "0.0.0"
        print("[resolve_version] WARNING: Could not resolve version, using 0.0.0", file=sys.stderr)

    # Validate semver-ish format
    if not re.match(r"^\d+\.\d+\.\d+", version):
        print(
            f"[resolve_version] WARNING: Version '{version}' does not match semver format",
            file=sys.stderr,
        )

    # Output just the version string (for shell $(...) capture)
    print(version)


if __name__ == "__main__":
    main()
