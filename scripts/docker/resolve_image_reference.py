#!/usr/bin/env python3
"""
resolve_image_reference.py
Resolve a target platform to an image variant and full image reference.

Responsibilities:
- Map build target platform → Docker image variant
- Load and parse image manifest (from file or registry)
- Enforce immutable digest references in release mode
- Validate image contract version compatibility
- Reject unsupported targets (iOS, Windows64) with clear errors

Usage (standalone):
  python3 scripts/docker/resolve_image_reference.py \
    --target-platform Android \
    --unity-version 2022.3.21f1 \
    --registry ghcr.io/myorg \
    [--manifest-path .docker/image-manifest.json] \
    [--release-mode] \
    [--image-variant android] \
    [--image-digest sha256:...]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Constants ──────────────────────────────────────────────────────────────

IMAGE_CONTRACT_VERSION = "1"

# Platform → variant mapping
PLATFORM_VARIANT_MAP: Dict[str, str] = {
    "Android": "android",
    "WebGL": "webgl",
    "StandaloneLinux64": "linux",
    "LinuxServer": "linux",
    # Supported variants without a specific platform target
    "Linux64": "linux",
}

# Platforms that are NOT supported in Docker (require native tools/licences)
UNSUPPORTED_PLATFORMS: Dict[str, str] = {
    "iOS": (
        "iOS builds require macOS and Xcode — Docker is not supported. "
        "Use the native iOS workflow (ios-build.yml)."
    ),
    "Windows64": (
        "Windows64 IL2CPP cross-compilation is not yet available in Docker. "
        "Use the windows-build runner or a Windows agent."
    ),
}

SUPPORTED_VARIANTS = {"base", "android", "webgl", "linux"}

# Minimum image contract version this tooling can consume
MIN_CONTRACT_VERSION = 1


# ── Image manifest helpers ─────────────────────────────────────────────────

def load_manifest_from_file(manifest_path: Path) -> Dict[str, Any]:
    """Load image manifest JSON from a local file."""
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Image manifest not found: {manifest_path}")
    try:
        with open(manifest_path) as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in image manifest {manifest_path}: {exc}") from exc


def load_manifest_from_label(image_ref: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to pull image manifest data from the Docker image label
    'org.unity.build.manifest'.  Returns None if docker is unavailable or
    the label is absent.
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format",
             "{{index .Config.Labels \"org.unity.build.manifest\"}}", image_ref],
            capture_output=True,
            text=True,
            timeout=30,
        )
        label_value = result.stdout.strip()
        if label_value:
            return json.loads(label_value)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


# ── Validation helpers ─────────────────────────────────────────────────────

def validate_contract_version(manifest: Dict[str, Any]) -> None:
    """Raise if the manifest's contract version is incompatible."""
    contract_version_str = manifest.get("image_contract_version", "1")
    try:
        contract_version = int(str(contract_version_str).split(".")[0])
    except ValueError:
        raise ValueError(
            f"image_contract_version '{contract_version_str}' is not a valid integer."
        )
    if contract_version < MIN_CONTRACT_VERSION:
        raise ValueError(
            f"Image contract version {contract_version} is below the minimum "
            f"required version {MIN_CONTRACT_VERSION}. Rebuild the image."
        )


def enforce_immutable_reference(
    image_ref: str,
    digest: Optional[str],
    release_mode: bool,
) -> str:
    """
    In release mode, reject mutable tags (latest, edge, etc.) and require a digest.
    Returns the pinned image reference (with digest appended if provided separately).
    """
    if not release_mode:
        return image_ref

    # A digest reference contains '@sha256:'
    has_digest_in_ref = "@sha256:" in image_ref
    has_separate_digest = bool(digest)

    if not has_digest_in_ref and not has_separate_digest:
        raise ValueError(
            "release-mode requires an immutable image reference. "
            "Provide --image-digest sha256:<hash> or use an @sha256: pinned reference."
        )

    # Reject obviously mutable tags
    mutable_tags = {"latest", "edge", "main", "master", "dev", "development", "staging"}
    if ":" in image_ref and "@" not in image_ref:
        tag = image_ref.rsplit(":", 1)[-1]
        if tag.lower() in mutable_tags:
            raise ValueError(
                f"release-mode forbids mutable tag '{tag}'. "
                "Pin the image with a digest (@sha256:...) instead."
            )

    # Append digest if provided separately and not already embedded
    if has_separate_digest and not has_digest_in_ref:
        # Strip any existing tag before appending digest
        base = image_ref.split(":")[0] if ":" in image_ref else image_ref
        return f"{base}@{digest}"

    return image_ref


# ── Core resolution logic ──────────────────────────────────────────────────

def resolve(
    target_platform: str,
    unity_version: str,
    registry: str,
    image_variant: Optional[str] = None,
    image_digest: Optional[str] = None,
    manifest_path: Optional[Path] = None,
    release_mode: bool = False,
) -> Dict[str, Any]:
    """
    Resolve target platform to a full Docker image reference.

    Returns a dict with keys:
      image_ref       – full pullable image reference
      digest          – sha256 digest (if known)
      variant         – image variant name (android/webgl/linux/base)
      supported_targets – list of platforms this image supports
      unity_version   – Unity version embedded in image
    """
    # 1. Reject unsupported platforms early with clear guidance
    if target_platform in UNSUPPORTED_PLATFORMS:
        raise ValueError(
            f"Platform '{target_platform}' is not supported in Docker builds. "
            + UNSUPPORTED_PLATFORMS[target_platform]
        )

    # 2. Resolve variant
    if image_variant:
        variant = image_variant
        if variant not in SUPPORTED_VARIANTS:
            raise ValueError(
                f"Unknown image variant '{variant}'. "
                f"Supported variants: {', '.join(sorted(SUPPORTED_VARIANTS))}"
            )
    else:
        variant = PLATFORM_VARIANT_MAP.get(target_platform)
        if variant is None:
            raise ValueError(
                f"No Docker variant mapping for platform '{target_platform}'. "
                f"Supported platforms: {', '.join(sorted(PLATFORM_VARIANT_MAP.keys()))}. "
                "Use --image-variant to specify manually."
            )

    # 3. Load manifest (file takes priority, then registry label probe)
    manifest: Optional[Dict[str, Any]] = None
    if manifest_path:
        manifest = load_manifest_from_file(manifest_path)
    else:
        # Try a default location
        default_manifest = Path(".docker/image-manifest.json")
        if default_manifest.is_file():
            manifest = load_manifest_from_file(default_manifest)

    # 4. Build image tag from manifest or convention
    sanitized_version = unity_version.replace(".", "-")
    default_tag = f"{unity_version}-{variant}"

    if manifest:
        validate_contract_version(manifest)
        images = manifest.get("images", {})
        variant_info = images.get(variant, {})
        tag = variant_info.get("tag", default_tag)
        digest_from_manifest = variant_info.get("digest", "")
        supported_targets = variant_info.get("supported_targets", [target_platform])
        embedded_unity_version = variant_info.get("unity_version", unity_version)
        registry_from_manifest = manifest.get("registry", registry)

        # Validate unity version match
        if embedded_unity_version and embedded_unity_version != unity_version:
            raise ValueError(
                f"Unity version mismatch: requested {unity_version} but "
                f"manifest specifies {embedded_unity_version} for variant '{variant}'. "
                "Rebuild the image or update the manifest."
            )

        # Use digest from manifest if not provided explicitly
        if not image_digest and digest_from_manifest:
            image_digest = digest_from_manifest

        image_ref = f"{registry_from_manifest}/unity-build:{tag}"
    else:
        # No manifest — build reference from convention
        image_ref = f"{registry}/unity-build:{default_tag}"
        supported_targets = list(
            k for k, v in PLATFORM_VARIANT_MAP.items() if v == variant
        )

    # 5. Enforce immutability in release mode
    image_ref = enforce_immutable_reference(image_ref, image_digest, release_mode)

    return {
        "image_ref": image_ref,
        "digest": image_digest or "",
        "variant": variant,
        "supported_targets": supported_targets,
        "unity_version": unity_version,
    }


# ── CLI entry point ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve a Unity build target platform to a Docker image reference.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--target-platform", required=True,
                        help="Unity target platform (Android, WebGL, StandaloneLinux64, …)")
    parser.add_argument("--unity-version", required=True,
                        help="Unity Editor version (e.g. 2022.3.21f1)")
    parser.add_argument("--registry", default="ghcr.io/buzzell-studio",
                        help="Docker image registry prefix")
    parser.add_argument("--image-variant",
                        help="Force a specific image variant (base/android/webgl/linux)")
    parser.add_argument("--image-digest",
                        help="Expected sha256 digest for pinning (e.g. sha256:abc123…)")
    parser.add_argument("--manifest-path",
                        help="Path to image manifest JSON file")
    parser.add_argument("--release-mode", action="store_true",
                        help="Enforce immutable digest references (required for releases)")
    parser.add_argument("--output-json", action="store_true",
                        help="Output result as JSON (machine-readable)")
    args = parser.parse_args()

    manifest_path = Path(args.manifest_path) if args.manifest_path else None

    try:
        result = resolve(
            target_platform=args.target_platform,
            unity_version=args.unity_version,
            registry=args.registry,
            image_variant=args.image_variant,
            image_digest=args.image_digest,
            manifest_path=manifest_path,
            release_mode=args.release_mode,
        )
    except (ValueError, FileNotFoundError) as exc:
        if args.output_json:
            print(json.dumps({"error": str(exc)}))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[resolve_image_reference] Resolved:")
        print(f"  Platform  : {args.target_platform}")
        print(f"  Variant   : {result['variant']}")
        print(f"  Image ref : {result['image_ref']}")
        if result["digest"]:
            print(f"  Digest    : {result['digest']}")
        print(f"  Supported : {', '.join(result['supported_targets'])}")


if __name__ == "__main__":
    main()
