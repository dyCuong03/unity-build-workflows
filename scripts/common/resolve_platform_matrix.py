#!/usr/bin/env python3
"""Resolve multi-platform build matrix for unity-build-multi.yml.

Given a platform selection string, outputs:
  docker-platforms: JSON array of Docker-based (ubuntu) platforms
  run-ios:          "true" | "false"

Supported platform values:
  All         → all Docker platforms + iOS
  Android     → ["Android"] + no iOS
  WebGL       → ["WebGL"] + no iOS
  Linux64     → ["Linux64"] + no iOS
  LinuxServer → ["LinuxServer"] + no iOS
  iOS         → [] + iOS

Usage:
  python3 resolve_platform_matrix.py --platform All
  python3 resolve_platform_matrix.py --platform Android --output-format github-actions
"""

import argparse
import json
import os
import sys

DOCKER_PLATFORMS = ["Android", "WebGL", "Linux64", "LinuxServer"]
IOS_PLATFORM = "iOS"
ALL_OPTION = "All"
VALID_INPUTS = [ALL_OPTION] + DOCKER_PLATFORMS + [IOS_PLATFORM]


def resolve(platform: str) -> tuple:
    """Return (docker_platforms_list, run_ios_bool)."""
    if platform == ALL_OPTION:
        return list(DOCKER_PLATFORMS), True
    if platform in DOCKER_PLATFORMS:
        return [platform], False
    if platform == IOS_PLATFORM:
        return [], True
    raise ValueError(
        f"Unsupported platform: '{platform}'.\n"
        f"Valid values: {', '.join(VALID_INPUTS)}"
    )


def write_github_output(key: str, value: str) -> None:
    """Write a key=value pair to $GITHUB_OUTPUT if available."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve Unity multi-platform build matrix"
    )
    parser.add_argument(
        "--platform",
        required=True,
        help=f"Platform selection. One of: {', '.join(VALID_INPUTS)}",
    )
    parser.add_argument(
        "--output-format",
        choices=["github-actions", "json"],
        default="github-actions",
        help="Output format (default: github-actions → writes to $GITHUB_OUTPUT)",
    )
    args = parser.parse_args()

    try:
        docker_platforms, run_ios = resolve(args.platform)
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    docker_json = json.dumps(docker_platforms, separators=(",", ":"))
    run_ios_str = str(run_ios).lower()

    if args.output_format == "github-actions":
        # Echo to stdout for visibility in logs
        print(f"docker-platforms={docker_json}")
        print(f"run-ios={run_ios_str}")
        # Write to GITHUB_OUTPUT for downstream job consumption
        write_github_output("docker-platforms", docker_json)
        write_github_output("run-ios", run_ios_str)
    else:
        print(json.dumps({"docker-platforms": docker_platforms, "run-ios": run_ios}))

    return 0


if __name__ == "__main__":
    sys.exit(main())
