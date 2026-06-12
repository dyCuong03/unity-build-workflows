#!/usr/bin/env python3
"""
run_unity_build.py
Local build helper: finds the Unity editor, validates arguments,
calls BuildCommand.Execute, and streams logs to stdout.

Usage:
  python3 scripts/run_unity_build.py \
    --project-path . \
    --platform Android \
    --environment development \
    --version 1.0.0 \
    [--unity-version 2022.3.0f1] \
    [--build-path ./build/android] \
    [--dry-run]
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_PLATFORMS = ["Android", "iOS", "Windows64", "WebGL", "StandaloneLinux64"]
UNITY_TARGET_MAP = {
    "Android": "Android",
    "iOS": "iOS",
    "Windows64": "Win64",
    "WebGL": "WebGL",
    "StandaloneLinux64": "StandaloneLinux64",
}


def find_unity_executable(version: str | None = None) -> str | None:
    """
    Locate a Unity Editor executable.
    Priority: env var UNITY_EDITOR_PATH > Unity Hub > PATH symlink.
    """
    # 1. Explicit env override
    env_path = os.environ.get("UNITY_EDITOR_PATH", "")
    if env_path and Path(env_path).is_file():
        return env_path

    # 2. Unity Hub search paths per OS
    system = platform.system()
    search_dirs: list[Path] = []

    if system == "Darwin":  # macOS
        hub_editors = Path("/Applications/Unity/Hub/Editor")
        if hub_editors.is_dir():
            search_dirs = sorted(hub_editors.iterdir(), reverse=True)
        if version:
            candidate = Path(f"/Applications/Unity/Hub/Editor/{version}/Unity.app/Contents/MacOS/Unity")
            if candidate.is_file():
                return str(candidate)
        for d in search_dirs:
            candidate = d / "Unity.app" / "Contents" / "MacOS" / "Unity"
            if candidate.is_file():
                if version is None or version in str(d):
                    return str(candidate)

    elif system == "Windows":
        base_dirs = [
            Path("C:/Program Files/Unity/Hub/Editor"),
            Path(os.environ.get("LOCALAPPDATA", "C:/Users/User/AppData/Local")) / "Programs" / "Unity" / "Hub" / "Editor",
        ]
        for base in base_dirs:
            if base.is_dir():
                for d in sorted(base.iterdir(), reverse=True):
                    candidate = d / "Editor" / "Unity.exe"
                    if candidate.is_file():
                        if version is None or version in d.name:
                            return str(candidate)

    elif system == "Linux":
        # GitHub Actions Unity installs via Unity Hub
        hub_editors = Path.home() / ".local" / "share" / "unity-hub" / "editors"
        if hub_editors.is_dir():
            for d in sorted(hub_editors.iterdir(), reverse=True):
                candidate = d / "Editor" / "Unity"
                if candidate.is_file():
                    if version is None or version in d.name:
                        return str(candidate)
        # Symlink from CI setup action
        symlink = Path("/usr/local/bin/unity-editor")
        if symlink.is_file() or symlink.is_symlink():
            return str(symlink)

    # 3. PATH fallback
    which = shutil.which("unity-editor") or shutil.which("Unity")
    return which


def stream_process(proc: subprocess.Popen) -> int:
    """Stream stdout/stderr from process, return exit code."""
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
    proc.wait()
    return proc.returncode


def validate_args(args: argparse.Namespace) -> None:
    if args.platform not in SUPPORTED_PLATFORMS:
        print(f"ERROR: Unsupported platform '{args.platform}'. Choose from: {', '.join(SUPPORTED_PLATFORMS)}")
        sys.exit(1)
    project_path = Path(args.project_path)
    if not project_path.is_dir():
        print(f"ERROR: Project path not found: {project_path}")
        sys.exit(1)
    assets_dir = project_path / "Assets"
    if not assets_dir.is_dir():
        print(f"ERROR: No Assets/ directory found in {project_path} — is this a Unity project?")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Unity build helper")
    parser.add_argument("--project-path", default=".", help="Unity project root directory")
    parser.add_argument(
        "--platform",
        required=True,
        choices=SUPPORTED_PLATFORMS,
        help="Target build platform",
    )
    parser.add_argument("--environment", default="development", help="Build environment")
    parser.add_argument("--version", default="0.0.0", help="Build version string")
    parser.add_argument("--unity-version", default="", help="Unity editor version hint")
    parser.add_argument("--build-path", default="", help="Build output path")
    parser.add_argument("--build-method", default="BuildCommand.Execute", help="Unity static method to call")
    parser.add_argument("--dry-run", action="store_true", help="Print command without running")
    parser.add_argument("--log-file", default="", help="Unity log output file (default: stdout)")
    args = parser.parse_args()

    validate_args(args)

    # Find Unity
    unity_exec = find_unity_executable(args.unity_version or None)
    if not unity_exec:
        print("ERROR: Unity Editor not found. Set UNITY_EDITOR_PATH or install via Unity Hub.")
        sys.exit(1)
    print(f"[run_unity_build] Unity: {unity_exec}")

    # Resolve paths
    project_path = str(Path(args.project_path).resolve())
    build_path = args.build_path or str(Path("./build") / args.platform.lower())
    Path(build_path).mkdir(parents=True, exist_ok=True)
    log_file = args.log_file or "-"  # "-" means stdout

    unity_target = UNITY_TARGET_MAP[args.platform]

    # Build command
    cmd = [
        unity_exec,
        "-batchmode",
        "-nographics",
        "-projectPath", project_path,
        "-executeMethod", args.build_method,
        "-buildTarget", unity_target,
        "-buildPath", build_path,
        "-buildVersion", args.version,
        "-buildEnvironment", args.environment,
        "-quit",
    ]

    if log_file != "-":
        cmd += ["-logFile", log_file]
    else:
        cmd += ["-logFile", "-"]

    print(f"[run_unity_build] Command: {' '.join(cmd)}")

    if args.dry_run:
        print("[run_unity_build] DRY RUN — not executing")
        return

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    exit_code = stream_process(proc)

    if exit_code != 0:
        print(f"[run_unity_build] Build failed with exit code {exit_code}", file=sys.stderr)
        sys.exit(exit_code)

    print(f"[run_unity_build] Build succeeded. Output: {build_path}")


if __name__ == "__main__":
    main()
