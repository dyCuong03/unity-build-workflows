#!/usr/bin/env python3
"""
resolve_platform_executor.py
Single source of truth for mapping a Unity build target platform to its
required CI executor.

Executors
---------
  docker-unity          — Linux container (Android, WebGL, Linux64, LinuxServer)
  macos-unity-xcode     — Approved macOS runner with Xcode + Unity iOS Build Support (iOS only)

Windows64 is explicitly unsupported; no executor is assigned.

Usage:
  python3 scripts/common/resolve_platform_executor.py \\
    --target-platform iOS [--runner-os macos]
  python3 scripts/common/resolve_platform_executor.py \\
    --target-platform Android [--runner-os linux]

Exit 0 and prints executor name on success.
Exit 1 and prints contract error to stderr on violation.
"""

import argparse
import sys

# ── Executor names ─────────────────────────────────────────────────────────

EXECUTOR_DOCKER: str = "docker-unity"
EXECUTOR_MACOS: str = "macos-unity-xcode"

# ── Platform classification ────────────────────────────────────────────────

# Platforms that MUST execute inside the Docker Unity executor (Linux).
# No other executor is permitted for these targets.
DOCKER_PLATFORMS = frozenset({"Android", "WebGL", "StandaloneLinux64", "LinuxServer", "Linux64"})

# Platforms that MUST execute on the approved macOS runner with Xcode.
# Linux/Docker execution is explicitly prohibited.
MACOS_PLATFORMS = frozenset({"iOS"})

# Platforms that are explicitly unsupported — no executor is assigned and
# the pipeline must reject them at the earliest possible gate.
UNSUPPORTED_PLATFORMS = frozenset({"Windows64"})

# Runner OS identifiers that map to "Linux / Docker" for cross-validation.
_LINUX_RUNNER_ALIASES = frozenset({"linux", "ubuntu", "docker"})


# ── Contract error factories ───────────────────────────────────────────────

def _ios_on_linux_error(platform: str = "iOS") -> str:
    """
    Exact contract message when a macOS-only platform is requested on Linux.

    The literal string is tested by downstream guards in run_unity_container.py
    and any workflow-level gating scripts — do not change without updating those.
    """
    return (
        f"Target `{platform}` requires an approved macOS runner with Xcode and "
        f"Unity iOS Build Support. Linux Docker execution is not supported."
    )


def _docker_platform_on_native_error(platform: str) -> str:
    """
    Exact contract message when a Docker-only platform is run natively.

    The literal string is tested by downstream guards — do not change without
    updating those.
    """
    return (
        f"Target `{platform}` must use the Docker Unity executor. "
        f"Native Unity execution is prohibited."
    )


# ── Core resolver ──────────────────────────────────────────────────────────

def resolve_executor(target_platform: str, runner_os: str = None) -> str:
    """
    Resolve the required CI executor for a Unity build target platform.

    Parameters
    ----------
    target_platform : str
        Unity build target (e.g. "Android", "iOS", "WebGL", "StandaloneLinux64").
    runner_os : str, optional
        The OS of the requesting runner (e.g. "linux", "macos", "windows").
        When provided, cross-validates that the runner is compatible with the
        resolved executor and raises a contract error if not.

    Returns
    -------
    str
        "docker-unity" for Docker-mandatory platforms.
        "macos-unity-xcode" for iOS.

    Raises
    ------
    ValueError
        With the exact contract error string when:
        - An iOS platform is requested on a Linux/Docker runner.
        - A Docker-only platform is requested on a non-Linux (native) runner.
        - The platform is explicitly unsupported (Windows64).
        - The platform is unknown.
    """
    runner_os_lower = (runner_os or "").lower().strip()

    # ── Explicitly unsupported ─────────────────────────────────────────────
    if target_platform in UNSUPPORTED_PLATFORMS:
        raise ValueError(
            f"Target `{target_platform}` is explicitly unsupported in this pipeline. "
            "Windows64 IL2CPP cross-compilation is not supported on any executor."
        )

    # ── macOS-only platforms (iOS) ─────────────────────────────────────────
    if target_platform in MACOS_PLATFORMS:
        # Cross-validate: if caller is explicitly on Linux/Docker, contract violation
        if runner_os_lower and runner_os_lower in _LINUX_RUNNER_ALIASES:
            raise ValueError(_ios_on_linux_error(target_platform))
        return EXECUTOR_MACOS

    # ── Docker-only platforms (Android, WebGL, Linux*) ─────────────────────
    if target_platform in DOCKER_PLATFORMS:
        # Cross-validate: non-Linux native runner is a contract violation
        if runner_os_lower and runner_os_lower not in _LINUX_RUNNER_ALIASES:
            raise ValueError(_docker_platform_on_native_error(target_platform))
        return EXECUTOR_DOCKER

    # ── Unknown platform ───────────────────────────────────────────────────
    supported = sorted(DOCKER_PLATFORMS | MACOS_PLATFORMS)
    raise ValueError(
        f"Unknown target platform '{target_platform}'. "
        f"Supported platforms: {', '.join(supported)}. "
        f"Windows64 is explicitly unsupported."
    )


# ── CLI entry point ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the required CI executor for a Unity build target platform.\n\n"
            "Prints the executor name on stdout and exits 0 on success.\n"
            "Prints a contract error to stderr and exits 1 on violation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Android → docker-unity
  python3 scripts/common/resolve_platform_executor.py --target-platform Android

  # iOS on macOS → macos-unity-xcode
  python3 scripts/common/resolve_platform_executor.py --target-platform iOS --runner-os macos

  # iOS on Linux → contract error (exit 1)
  python3 scripts/common/resolve_platform_executor.py --target-platform iOS --runner-os linux

  # Android on macOS → contract error (exit 1)
  python3 scripts/common/resolve_platform_executor.py --target-platform Android --runner-os macos
""",
    )
    parser.add_argument(
        "--target-platform",
        required=True,
        help="Unity build target platform (Android, WebGL, iOS, StandaloneLinux64, …)",
    )
    parser.add_argument(
        "--runner-os",
        required=False,
        default=None,
        help="Runner OS for cross-validation (linux, macos, windows). Omit to skip cross-validation.",
    )
    args = parser.parse_args()

    try:
        executor = resolve_executor(args.target_platform, args.runner_os)
        print(executor)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
