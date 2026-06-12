#!/usr/bin/env python3
"""
run_unity_build.py  (DEPRECATED)
─────────────────────────────────────────────────────────────────────────────
This script is a backward-compatibility shim retained during the transition
to Docker-mandatory builds.

ALL Unity builds now run inside Docker.
Please use the Docker wrapper directly:

  python3 scripts/docker/run_unity_container.py \\
    --project-path . \\
    --unity-version <version> \\
    --target-platform <platform> \\
    --environment <env> \\
    [--output-path ./build] \\
    [--dry-run]

Argument mapping (this shim → Docker wrapper):
  --project-path   → --project-path      (unchanged)
  --platform       → --target-platform
  --environment    → --environment        (unchanged)
  --version        → (passed as BUILD_VERSION env var inside container)
  --unity-version  → --unity-version      (unchanged)
  --build-path     → --output-path
  --dry-run        → --dry-run            (unchanged)

Arguments with no Docker equivalent (--build-method, --log-file) are
silently ignored — the container entrypoint controls those internally.
─────────────────────────────────────────────────────────────────────────────
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

SUPPORTED_PLATFORMS = ["Android", "iOS", "Windows64", "WebGL", "StandaloneLinux64"]

_DEPRECATION_BANNER = """\
╔══════════════════════════════════════════════════════════════════╗
║  DEPRECATION WARNING                                             ║
║  run_unity_build.py is deprecated and will be removed.          ║
║  Use: python3 scripts/docker/run_unity_container.py             ║
║  See: docs/docker-migration.md for the migration guide.         ║
╚══════════════════════════════════════════════════════════════════╝
"""


def _print_deprecation() -> None:
    print(_DEPRECATION_BANNER, file=sys.stderr)


def _build_docker_args(args: argparse.Namespace) -> list:
    """Translate legacy args to run_unity_container.py args."""
    wrapper = Path(__file__).parent / "docker" / "run_unity_container.py"
    cmd = [sys.executable, str(wrapper)]

    cmd += ["--project-path", args.project_path]
    cmd += ["--target-platform", args.platform]
    cmd += ["--environment", args.environment]

    if args.unity_version:
        cmd += ["--unity-version", args.unity_version]
    else:
        # Unity version is required by the Docker wrapper; caller must supply it
        # via UNITY_VERSION env var or --unity-version.
        unity_version = os.environ.get("UNITY_VERSION", "")
        if not unity_version:
            print(
                "ERROR: --unity-version is required for Docker builds. "
                "Set --unity-version or the UNITY_VERSION environment variable.",
                file=sys.stderr,
            )
            sys.exit(1)
        cmd += ["--unity-version", unity_version]

    if args.build_path:
        cmd += ["--output-path", args.build_path]

    if args.dry_run:
        cmd += ["--dry-run"]

    # Pass build version as environment variable (container reads BUILD_VERSION)
    if args.version and args.version != "0.0.0":
        os.environ.setdefault("BUILD_VERSION", args.version)

    return cmd


def main() -> None:
    _print_deprecation()

    parser = argparse.ArgumentParser(
        description=(
            "[DEPRECATED] Native Unity build helper — now delegates to Docker. "
            "Use scripts/docker/run_unity_container.py directly."
        )
    )
    parser.add_argument("--project-path", default=".", help="Unity project root directory")
    parser.add_argument(
        "--platform",
        required=True,
        choices=SUPPORTED_PLATFORMS,
        help="Target build platform",
    )
    parser.add_argument("--environment", default="development", help="Build environment")
    parser.add_argument("--version", default="0.0.0", help="Build version string")
    parser.add_argument("--unity-version", default="", help="Unity editor version")
    parser.add_argument("--build-path", default="", help="Build output path")
    # Kept for CLI compat but ignored — container handles these internally
    parser.add_argument("--build-method", default="BuildCommand.Execute",
                        help="[IGNORED] Unity static method (handled by container entrypoint)")
    parser.add_argument("--log-file", default="",
                        help="[IGNORED] Log file path (container streams to stdout)")
    parser.add_argument("--dry-run", action="store_true", help="Print command without running")
    args = parser.parse_args()

    docker_cmd = _build_docker_args(args)

    print(
        f"[run_unity_build] Delegating to Docker wrapper: {' '.join(docker_cmd[:3])} …",
        file=sys.stderr,
    )

    result = subprocess.run(docker_cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
