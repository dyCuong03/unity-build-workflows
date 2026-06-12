#!/usr/bin/env python3
"""
build_unity_image.py
Build a Unity Docker image for a specific variant using BuildKit.

Produces a tagged image and writes an image-manifest.json that downstream
tools (run_unity_container.py, validate_unity_image.py) consume.

Usage:
  python3 scripts/docker/build_unity_image.py \\
    --variant android \\
    --unity-version 2022.3.21f1 \\
    --registry ghcr.io/myorg \\
    [--tag 2022.3.21f1-android] \\
    [--push] \\
    [--scan] \\
    [--dockerfile-dir .docker/]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# ── Constants ──────────────────────────────────────────────────────────────

SUPPORTED_VARIANTS = ["base", "android", "webgl", "linux"]
IMAGE_CONTRACT_VERSION = "1"

# Map variant → Dockerfile name convention
DOCKERFILE_MAP: Dict[str, str] = {
    "base":    "Dockerfile.base",
    "android": "Dockerfile.android",
    "webgl":   "Dockerfile.webgl",
    "linux":   "Dockerfile.linux",
}

# Platforms each variant supports (for manifest generation)
VARIANT_SUPPORTED_TARGETS: Dict[str, List[str]] = {
    "base":    ["StandaloneLinux64"],
    "android": ["Android"],
    "webgl":   ["WebGL"],
    "linux":   ["StandaloneLinux64", "LinuxServer"],
}


# ── Helpers ────────────────────────────────────────────────────────────────

def _abort(message: str, exit_code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(exit_code)


def _log(message: str) -> None:
    print(f"[build_unity_image] {message}", flush=True)


def _require_docker() -> str:
    docker = shutil.which("docker")
    if not docker:
        _abort("docker executable not found in PATH.")
    return docker  # type: ignore[return-value]


def _dockerfile_path(variant: str, dockerfile_dir: Path) -> Path:
    """Locate the Dockerfile for the given variant."""
    filename = DOCKERFILE_MAP[variant]
    candidate = dockerfile_dir / filename
    if candidate.is_file():
        return candidate

    # Also try .docker/ relative to repo root
    alt = Path(".docker") / filename
    if alt.is_file():
        return alt

    _abort(
        f"Dockerfile for variant '{variant}' not found. "
        f"Expected: {candidate} or {alt}. "
        "Place Dockerfiles in --dockerfile-dir or .docker/."
    )
    return candidate  # unreachable


def _build_image_tag(registry: str, unity_version: str, variant: str, custom_tag: Optional[str]) -> str:
    if custom_tag:
        return f"{registry}/unity-build:{custom_tag}"
    return f"{registry}/unity-build:{unity_version}-{variant}"


def _oci_labels(unity_version: str, variant: str, registry: str) -> Dict[str, str]:
    """Standard OCI image labels."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "org.opencontainers.image.title": f"Unity Build Image ({variant})",
        "org.opencontainers.image.description": (
            f"Unity {unity_version} Docker image for {variant} builds"
        ),
        "org.opencontainers.image.version": unity_version,
        "org.opencontainers.image.created": now,
        "org.opencontainers.image.vendor": "BuzzelStudio",
        "org.unity.build.unity-version": unity_version,
        "org.unity.build.variant": variant,
        "org.unity.build.contract-version": IMAGE_CONTRACT_VERSION,
    }


def _get_image_digest(docker: str, full_tag: str) -> str:
    """Retrieve the sha256 digest of a locally built image."""
    try:
        result = subprocess.run(
            [docker, "inspect", "--format", "{{index .RepoDigests 0}}", full_tag],
            capture_output=True, text=True, timeout=15,
        )
        digest_line = result.stdout.strip()
        # Format: registry/image@sha256:xxx
        if "@sha256:" in digest_line:
            return "sha256:" + digest_line.split("@sha256:")[-1]
    except Exception:
        pass

    # Fallback: image ID hash
    try:
        result = subprocess.run(
            [docker, "inspect", "--format", "{{.Id}}", full_tag],
            capture_output=True, text=True, timeout=15,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _write_manifest(
    manifest_path: Path,
    variant: str,
    unity_version: str,
    full_tag: str,
    digest: str,
    registry: str,
) -> None:
    """Write/update the image-manifest.json consumed by run_unity_container.py."""
    manifest: Dict = {}
    if manifest_path.is_file():
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    manifest.setdefault("image_contract_version", IMAGE_CONTRACT_VERSION)
    manifest.setdefault("registry", registry)
    manifest.setdefault("images", {})

    tag_part = full_tag.split(":", 1)[-1] if ":" in full_tag else full_tag
    manifest["images"][variant] = {
        "tag": tag_part,
        "digest": digest,
        "unity_version": unity_version,
        "supported_targets": VARIANT_SUPPORTED_TARGETS.get(variant, []),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    _log(f"Manifest updated: {manifest_path}")


def _run_scan(scanner_script: Path, full_tag: str) -> None:
    """Run the vulnerability scanner if the scan script exists."""
    if scanner_script.is_file():
        _log(f"Running vulnerability scan on {full_tag} …")
        result = subprocess.run(
            ["bash", str(scanner_script), full_tag, "HIGH"],
            text=True,
        )
        if result.returncode != 0:
            _abort(
                f"Vulnerability scan failed for {full_tag}. "
                "Review the scan report and remediate before pushing."
            )
    else:
        print(
            f"WARNING: scan_image.sh not found at {scanner_script}. "
            "Skipping vulnerability scan.",
            file=sys.stderr,
        )


# ── Main build logic ───────────────────────────────────────────────────────

def build_image(args: argparse.Namespace) -> None:
    docker = _require_docker()

    dockerfile_dir = Path(args.dockerfile_dir)
    dockerfile = _dockerfile_path(args.variant, dockerfile_dir)
    full_tag = _build_image_tag(args.registry, args.unity_version, args.variant, args.tag)

    _log(f"Building variant   : {args.variant}")
    _log(f"Unity version      : {args.unity_version}")
    _log(f"Image tag          : {full_tag}")
    _log(f"Dockerfile         : {dockerfile}")

    # ── Build command ──────────────────────────────────────────────────────
    cmd: List[str] = [docker, "build"]

    # Enable BuildKit
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"

    # Build args
    cmd += [
        "--build-arg", f"UNITY_VERSION={args.unity_version}",
        "--build-arg", f"VARIANT={args.variant}",
    ]

    # OCI labels
    for label_key, label_value in _oci_labels(args.unity_version, args.variant, args.registry).items():
        cmd += ["--label", f"{label_key}={label_value}"]

    # Tag
    cmd += ["--tag", full_tag]

    # Dockerfile and context
    cmd += ["--file", str(dockerfile)]
    cmd += [str(dockerfile_dir)]

    if args.no_cache:
        cmd += ["--no-cache"]

    if args.platform:
        cmd += ["--platform", args.platform]

    _log("Running: " + " ".join(cmd))

    if args.dry_run:
        _log("DRY RUN — not executing.")
        return

    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        _abort(f"docker build failed with exit code {result.returncode}.")

    _log(f"Image built: {full_tag}")

    # ── Retrieve digest ────────────────────────────────────────────────────
    digest = _get_image_digest(docker, full_tag)
    if digest:
        _log(f"Digest: {digest}")

    # ── Write manifest ─────────────────────────────────────────────────────
    manifest_path = Path(args.manifest_path)
    _write_manifest(manifest_path, args.variant, args.unity_version, full_tag, digest, args.registry)

    # ── Vulnerability scan ─────────────────────────────────────────────────
    if args.scan:
        scanner_script = Path(__file__).parent / "scan_image.sh"
        _run_scan(scanner_script, full_tag)

    # ── Push ───────────────────────────────────────────────────────────────
    if args.push:
        _log(f"Pushing {full_tag} …")
        push_result = subprocess.run([docker, "push", full_tag])
        if push_result.returncode != 0:
            _abort(f"docker push failed with exit code {push_result.returncode}.")

        # Fetch digest from registry after push
        registry_digest = _get_image_digest(docker, full_tag)
        if registry_digest and registry_digest != digest:
            _write_manifest(
                manifest_path, args.variant, args.unity_version,
                full_tag, registry_digest, args.registry,
            )
        _log(f"Pushed: {full_tag}")

    _log("Done.")


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a Unity Docker image for a specific variant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--variant", required=True, choices=SUPPORTED_VARIANTS,
                        help="Image variant to build")
    parser.add_argument("--unity-version", required=True,
                        help="Unity Editor version (e.g. 2022.3.21f1)")
    parser.add_argument("--registry", default="ghcr.io/buzzell-studio",
                        help="Docker registry prefix")
    parser.add_argument("--tag",
                        help="Custom image tag (default: <version>-<variant>)")
    parser.add_argument("--push", action="store_true",
                        help="Push the image to the registry after building")
    parser.add_argument("--scan", action="store_true",
                        help="Run vulnerability scan after building (requires scan_image.sh)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Build without Docker layer cache")
    parser.add_argument("--platform",
                        help="Target platform for multi-arch builds (e.g. linux/amd64)")
    parser.add_argument("--dockerfile-dir", default=".docker",
                        help="Directory containing Dockerfiles (default: .docker/)")
    parser.add_argument("--manifest-path", default=".docker/image-manifest.json",
                        help="Path to write/update image manifest JSON")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print build command without executing")
    args = parser.parse_args()

    build_image(args)


if __name__ == "__main__":
    main()
