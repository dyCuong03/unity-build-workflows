#!/usr/bin/env python3
"""
generate_build_metadata.py
Generate build-metadata.json for inclusion in the Unity build artifact.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path


def run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate build metadata JSON")
    parser.add_argument("--project-path", required=True, help="Unity project root")
    parser.add_argument("--platform", required=True, help="Target platform")
    parser.add_argument("--version", required=True, help="Build version string")
    parser.add_argument("--environment", default="development", help="Build environment")
    parser.add_argument("--build-number", default="0", help="CI build number")
    parser.add_argument("--commit", default="", help="Git commit SHA")
    parser.add_argument("--output-path", default="", help="Output file path (default: project-path/build-metadata.json)")
    args = parser.parse_args()

    project_path = Path(args.project_path).resolve()
    output_path = args.output_path or str(project_path / "build-metadata.json")

    # Gather git info
    commit_sha = args.commit or run_git(["rev-parse", "HEAD"], str(project_path))
    commit_short = commit_sha[:8] if commit_sha else ""
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], str(project_path))
    git_tag = run_git(["describe", "--tags", "--exact-match", "HEAD"], str(project_path))
    git_dirty = bool(run_git(["status", "--porcelain"], str(project_path)))

    # CI environment detection
    ci_provider = "unknown"
    ci_run_id = ""
    ci_run_url = ""
    if os.environ.get("GITHUB_ACTIONS"):
        ci_provider = "github-actions"
        ci_run_id = os.environ.get("GITHUB_RUN_ID", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        if repo and ci_run_id:
            ci_run_url = f"{server}/{repo}/actions/runs/{ci_run_id}"

    timestamp = datetime.datetime.utcnow().isoformat() + "Z"

    metadata = {
        "build": {
            "version": args.version,
            "number": int(args.build_number),
            "platform": args.platform,
            "environment": args.environment,
            "timestamp": timestamp,
        },
        "git": {
            "commit": commit_sha,
            "commit_short": commit_short,
            "branch": branch,
            "tag": git_tag,
            "dirty": git_dirty,
        },
        "ci": {
            "provider": ci_provider,
            "run_id": ci_run_id,
            "run_url": ci_run_url,
            "actor": os.environ.get("GITHUB_ACTOR", ""),
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        },
    }

    # Write output
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"[generate_build_metadata] Written to: {output_file}", file=sys.stderr)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
