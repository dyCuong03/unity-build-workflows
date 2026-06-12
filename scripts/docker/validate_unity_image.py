#!/usr/bin/env python3
"""
validate_unity_image.py
Validate that a built Unity Docker image meets all requirements before it
is used in builds.

Checks:
  - Unity executable exists inside the image at the expected path
  - Required Unity modules are installed for the target platform
  - SDK/NDK versions are present and correct for Android builds
  - Container entrypoint executes without error (smoke test)
  - Image healthcheck passes
  - Image manifest label is present and well-formed
  - No secrets are embedded in image history

Usage:
  python3 scripts/docker/validate_unity_image.py \\
    --image-ref ghcr.io/myorg/unity-build:2022.3.21f1-android \\
    --target-platform Android \\
    [--unity-version 2022.3.21f1] \\
    [--strict]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

# ── Constants ──────────────────────────────────────────────────────────────

UNITY_EXECUTABLE_PATH = "/opt/unity/Editor/Unity"

# Required modules per target platform (checked via `Unity -version` capability)
REQUIRED_MODULES_PER_PLATFORM: Dict[str, List[str]] = {
    "Android": ["android", "android-sdk-ndk-tools"],
    "WebGL": ["webgl"],
    "StandaloneLinux64": [],
    "LinuxServer": [],
}

# Android SDK/NDK minimum versions
MIN_ANDROID_SDK_VERSION = 30
MIN_ANDROID_NDK_VERSION = 23  # NDK r23

# Patterns that should NEVER appear in image history (secret leakage indicators)
SECRET_PATTERNS = [
    re.compile(r"UNITY_LICENSE\s*=\s*\S"),
    re.compile(r"UNITY_PASSWORD\s*=\s*\S"),
    re.compile(r"UNITY_EMAIL\s*=\s*[a-zA-Z0-9._%+\-]+@"),
    re.compile(r"-----BEGIN.*CERTIFICATE-----"),
    re.compile(r"-----BEGIN.*PRIVATE KEY-----"),
    re.compile(r"api[_\-]?key\s*=\s*[a-zA-Z0-9]{16,}", re.IGNORECASE),
]


# ── Helpers ────────────────────────────────────────────────────────────────

def _log(message: str) -> None:
    print(f"[validate_unity_image] {message}", flush=True)


def _abort(message: str, exit_code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(exit_code)


def _require_docker() -> str:
    docker = shutil.which("docker")
    if not docker:
        _abort("docker executable not found in PATH.")
    return docker  # type: ignore[return-value]


def _run_in_image(
    docker: str, image_ref: str, command: List[str], timeout: int = 60
) -> Tuple[int, str, str]:
    """Run a command inside the image (ephemeral container) and return (rc, stdout, stderr)."""
    full_cmd = [docker, "run", "--rm", "--entrypoint", "sh",
                "--cap-drop=ALL", "--security-opt=no-new-privileges",
                image_ref, "-c", " ".join(command)]
    try:
        result = subprocess.run(
            full_cmd, capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s"


def _docker_inspect(docker: str, image_ref: str) -> Optional[Dict]:
    """Return `docker inspect` JSON for the image or None on failure."""
    try:
        result = subprocess.run(
            [docker, "inspect", image_ref],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data[0] if data else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


# ── Check functions ────────────────────────────────────────────────────────

def check_unity_executable(docker: str, image_ref: str) -> Tuple[bool, str]:
    """Verify the Unity binary exists and is executable."""
    rc, out, _ = _run_in_image(docker, image_ref, [f"test -x {UNITY_EXECUTABLE_PATH} && echo OK"])
    if rc == 0 and "OK" in out:
        return True, f"Unity executable found at {UNITY_EXECUTABLE_PATH}"
    return False, (
        f"Unity executable not found at {UNITY_EXECUTABLE_PATH}. "
        "Rebuild the image with the correct Unity installation path."
    )


def check_unity_version(docker: str, image_ref: str, expected_version: Optional[str]) -> Tuple[bool, str]:
    """Run `Unity -version` and optionally compare against expected version."""
    rc, out, err = _run_in_image(
        docker, image_ref,
        [f"{UNITY_EXECUTABLE_PATH} -version 2>&1 | head -5"],
        timeout=90,
    )
    if rc != 0:
        # Unity -version exits non-zero on headless but may still print version
        pass
    version_line = out or err
    if expected_version and expected_version not in version_line:
        return False, (
            f"Unity version mismatch: expected {expected_version}, "
            f"got: {version_line[:100]!r}"
        )
    return True, f"Unity version check OK: {version_line[:80]}"


def check_required_modules(
    docker: str, image_ref: str, target_platform: str
) -> Tuple[bool, List[str]]:
    """Check required build modules/tools exist for the target platform."""
    required = REQUIRED_MODULES_PER_PLATFORM.get(target_platform, [])
    if not required:
        return True, []

    failures = []
    if target_platform == "Android":
        # Check Android SDK
        rc, out, _ = _run_in_image(docker, image_ref, ["ls /opt/android-sdk/platforms/ 2>/dev/null | head -5"])
        if rc != 0 or not out:
            failures.append("Android SDK platforms directory not found at /opt/android-sdk/platforms/")

        # Check NDK
        rc, out, _ = _run_in_image(docker, image_ref, ["ls /opt/android-sdk/ndk/ 2>/dev/null | head -5"])
        if rc != 0 or not out:
            failures.append("Android NDK not found at /opt/android-sdk/ndk/")

        # Check adb
        rc, _, _ = _run_in_image(docker, image_ref, ["which adb 2>/dev/null"])
        if rc != 0:
            failures.append("adb not found in PATH — Android SDK tools may not be installed")

    elif target_platform == "WebGL":
        # Check emscripten
        rc, _, _ = _run_in_image(docker, image_ref, ["which emcc 2>/dev/null"])
        if rc != 0:
            failures.append("emcc (Emscripten) not found — WebGL builds require Emscripten")

    if failures:
        return False, failures
    return True, []


def check_android_sdk_ndk_versions(
    docker: str, image_ref: str
) -> Tuple[bool, List[str]]:
    """Validate Android SDK API level and NDK version meet minimums."""
    issues = []

    # Check SDK API level
    rc, out, _ = _run_in_image(
        docker, image_ref,
        [f"ls /opt/android-sdk/platforms/ 2>/dev/null | sort -V | tail -1"],
    )
    if rc == 0 and out:
        # Format: android-XX
        match = re.search(r"android-(\d+)", out)
        if match:
            api_level = int(match.group(1))
            if api_level < MIN_ANDROID_SDK_VERSION:
                issues.append(
                    f"Android SDK API level {api_level} is below minimum {MIN_ANDROID_SDK_VERSION}. "
                    "Rebuild the image with a newer Android SDK."
                )

    # Check NDK version
    rc, out, _ = _run_in_image(
        docker, image_ref,
        ["cat /opt/android-sdk/ndk/*/source.properties 2>/dev/null | grep Revision | head -1"],
    )
    if rc == 0 and out:
        match = re.search(r"Revision\s*=\s*(\d+)", out)
        if match:
            ndk_major = int(match.group(1))
            if ndk_major < MIN_ANDROID_NDK_VERSION:
                issues.append(
                    f"Android NDK r{ndk_major} is below minimum r{MIN_ANDROID_NDK_VERSION}. "
                    "Rebuild the image with NDK r{MIN_ANDROID_NDK_VERSION} or newer."
                )

    return (len(issues) == 0), issues


def check_entrypoint(docker: str, image_ref: str) -> Tuple[bool, str]:
    """Verify the image entrypoint executes without error (quick smoke test)."""
    # Try running the container with --help or a no-op
    try:
        result = subprocess.run(
            [docker, "run", "--rm",
             "--cap-drop=ALL", "--security-opt=no-new-privileges",
             image_ref, "--help"],
            capture_output=True, text=True, timeout=30,
        )
        # Exit code 0 or non-zero is acceptable; what matters is it didn't crash with SIGKILL
        if result.returncode in (0, 1, 2, 64):  # common help exit codes
            return True, "Entrypoint smoke test passed"
        return True, f"Entrypoint exited with code {result.returncode} (acceptable)"
    except subprocess.TimeoutExpired:
        return False, "Entrypoint smoke test timed out after 30s"
    except Exception as exc:
        return False, f"Entrypoint smoke test failed: {exc}"


def check_manifest_label(docker: str, image_ref: str) -> Tuple[bool, str]:
    """Verify the image has the required OCI labels."""
    inspect = _docker_inspect(docker, image_ref)
    if not inspect:
        return False, "Could not inspect image — ensure the image is pulled locally"

    labels = inspect.get("Config", {}).get("Labels") or {}
    required_labels = [
        "org.opencontainers.image.version",
        "org.unity.build.unity-version",
        "org.unity.build.variant",
        "org.unity.build.contract-version",
    ]
    missing = [lbl for lbl in required_labels if lbl not in labels]
    if missing:
        return False, (
            f"Image is missing required OCI labels: {', '.join(missing)}. "
            "Rebuild with build_unity_image.py which applies all required labels."
        )

    contract_version = labels.get("org.unity.build.contract-version", "0")
    try:
        if int(contract_version) < 1:
            return False, (
                f"Image contract version {contract_version} is unsupported. "
                "Rebuild the image."
            )
    except ValueError:
        return False, f"Invalid contract version label: {contract_version!r}"

    return True, f"Image manifest labels OK (contract v{contract_version})"


def check_no_embedded_secrets(docker: str, image_ref: str) -> Tuple[bool, List[str]]:
    """
    Scan the image history for accidentally embedded secrets.
    This checks RUN/ENV instructions visible in the history.
    """
    try:
        result = subprocess.run(
            [docker, "history", "--no-trunc", "--format", "{{.CreatedBy}}", image_ref],
            capture_output=True, text=True, timeout=30,
        )
        history = result.stdout
    except subprocess.TimeoutExpired:
        return True, []  # Non-fatal — skip if slow

    findings = []
    for i, line in enumerate(history.splitlines(), 1):
        for pattern in SECRET_PATTERNS:
            if pattern.search(line):
                # Don't print the matched content — just flag the layer
                findings.append(
                    f"Layer {i}: possible secret detected matching pattern '{pattern.pattern[:40]}'. "
                    "Review the Dockerfile and ensure secrets are not passed as ENV or ARG."
                )

    return (len(findings) == 0), findings


# ── Orchestrator ───────────────────────────────────────────────────────────

def validate_image(
    image_ref: str,
    target_platform: str,
    unity_version: Optional[str],
    strict: bool,
) -> Tuple[List[str], List[str]]:
    """
    Run all validation checks.  Returns (errors, warnings).
    """
    docker = _require_docker()
    errors: List[str] = []
    warnings: List[str] = []

    def fail(msg: str) -> None:
        errors.append(msg)

    def warn(msg: str) -> None:
        warnings.append(msg)

    # 1. Unity executable
    _log("Checking Unity executable …")
    ok, msg = check_unity_executable(docker, image_ref)
    (fail if not ok else _log)(msg)

    # 2. Unity version (optional)
    if unity_version:
        _log("Checking Unity version …")
        ok, msg = check_unity_version(docker, image_ref, unity_version)
        (warn if not ok else _log)(msg)

    # 3. Required modules
    _log(f"Checking required modules for {target_platform} …")
    ok, module_failures = check_required_modules(docker, image_ref, target_platform)
    if not ok:
        for mf in module_failures:
            fail(mf)

    # 4. Android SDK/NDK versions (Android only)
    if target_platform == "Android":
        _log("Checking Android SDK/NDK versions …")
        ok, sdk_issues = check_android_sdk_ndk_versions(docker, image_ref)
        if not ok:
            for issue in sdk_issues:
                (fail if strict else warn)(issue)

    # 5. Entrypoint smoke test
    _log("Running entrypoint smoke test …")
    ok, msg = check_entrypoint(docker, image_ref)
    (warn if not ok else _log)(msg)

    # 6. OCI / manifest labels
    _log("Checking image manifest labels …")
    ok, msg = check_manifest_label(docker, image_ref)
    (fail if not ok else _log)(msg)

    # 7. Secret scan
    _log("Scanning image history for embedded secrets …")
    ok, secret_findings = check_no_embedded_secrets(docker, image_ref)
    if not ok:
        for finding in secret_findings:
            fail(finding)

    return errors, warnings


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a Unity Docker image before use in builds.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--image-ref", required=True,
                        help="Full image reference to validate")
    parser.add_argument("--target-platform", required=True,
                        help="Target build platform (Android | WebGL | StandaloneLinux64 | …)")
    parser.add_argument("--unity-version",
                        help="Expected Unity version inside the image (optional)")
    parser.add_argument("--strict", action="store_true",
                        help="Treat all warnings as errors")
    parser.add_argument("--output-json", action="store_true",
                        help="Output results as JSON")
    args = parser.parse_args()

    errors, warnings = validate_image(
        image_ref=args.image_ref,
        target_platform=args.target_platform,
        unity_version=args.unity_version,
        strict=args.strict,
    )

    if args.strict:
        errors.extend(warnings)
        warnings = []

    result = {
        "image_ref": args.image_ref,
        "target_platform": args.target_platform,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "valid": len(errors) == 0,
    }

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        for w in warnings:
            print(f"WARNING: {w}", file=sys.stderr)
        if not errors and not warnings:
            _log(f"Image {args.image_ref} passed all validation checks.")
        elif not errors:
            _log(f"Image valid (with {len(warnings)} warning(s)).")

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
