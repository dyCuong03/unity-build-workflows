"""
Tests for Docker image reference resolution (scripts/docker/resolve_image_reference.py).

Tests the public resolve() function, enforce_immutable_reference(),
validate_contract_version(), and load_manifest_from_file().

Covers:
- Android → android variant
- WebGL → webgl variant
- Linux64 → linux variant
- LinuxServer → linux variant
- StandaloneLinux64 → linux variant
- iOS → rejected with clear error
- Windows64 → rejected with clear error
- Unknown platform → rejected
- Release mode requires digest-pinned reference
- Mutable tags rejected in release mode
- Manifest file loaded and used correctly
- Contract version compatibility checked
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "docker"))


# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def resolver():
    try:
        import resolve_image_reference
        return resolve_image_reference
    except ImportError:
        pytest.skip("scripts/docker/resolve_image_reference.py not yet implemented")


# ---------------------------------------------------------------------------
# Resolve manifest (multi-variant lookup format used by resolve())
# ---------------------------------------------------------------------------

def _make_resolve_manifest(unity_version: str = "2022.3.45f1") -> Dict[str, Any]:
    """Build a minimal manifest in the format expected by resolve()."""
    return {
        "image_contract_version": "1",
        "registry": "ghcr.io/test",
        "images": {
            "android": {
                "tag": f"{unity_version}-android",
                "digest": "sha256:" + "a" * 64,
                "supported_targets": ["Android"],
                "unity_version": unity_version,
            },
            "webgl": {
                "tag": f"{unity_version}-webgl",
                "digest": "sha256:" + "b" * 64,
                "supported_targets": ["WebGL"],
                "unity_version": unity_version,
            },
            "linux": {
                "tag": f"{unity_version}-linux",
                "digest": "sha256:" + "c" * 64,
                "supported_targets": ["StandaloneLinux64", "LinuxServer", "Linux64"],
                "unity_version": unity_version,
            },
        },
    }


@pytest.fixture
def manifest_file(tmp_path) -> Path:
    """Write a valid resolve manifest to a temp file and return the path."""
    manifest = _make_resolve_manifest()
    path = tmp_path / "image-manifest.json"
    path.write_text(json.dumps(manifest))
    return path


# ---------------------------------------------------------------------------
# Platform → variant mapping
# ---------------------------------------------------------------------------

class TestPlatformToVariantMapping:

    def test_android_resolves_to_android_variant(self, resolver):
        result = resolver.resolve("Android", "2022.3.45f1", "ghcr.io/test")
        assert result["variant"] == "android"

    def test_webgl_resolves_to_webgl_variant(self, resolver):
        result = resolver.resolve("WebGL", "2022.3.45f1", "ghcr.io/test")
        assert result["variant"] == "webgl"

    def test_linux64_resolves_to_linux_variant(self, resolver):
        result = resolver.resolve("Linux64", "2022.3.45f1", "ghcr.io/test")
        assert result["variant"] == "linux"

    def test_standalonelinux64_resolves_to_linux_variant(self, resolver):
        result = resolver.resolve("StandaloneLinux64", "2022.3.45f1", "ghcr.io/test")
        assert result["variant"] == "linux"

    def test_linuxserver_resolves_to_linux_variant(self, resolver):
        result = resolver.resolve("LinuxServer", "2022.3.45f1", "ghcr.io/test")
        assert result["variant"] == "linux"

    def test_android_and_webgl_return_different_image_refs(self, resolver):
        android = resolver.resolve("Android", "2022.3.45f1", "ghcr.io/test")
        webgl = resolver.resolve("WebGL", "2022.3.45f1", "ghcr.io/test")
        assert android["image_ref"] != webgl["image_ref"]

    def test_resolve_returns_expected_keys(self, resolver):
        result = resolver.resolve("Android", "2022.3.45f1", "ghcr.io/test")
        assert "image_ref" in result
        assert "variant" in result
        assert "unity_version" in result


# ---------------------------------------------------------------------------
# Unsupported platform rejection
# ---------------------------------------------------------------------------

class TestUnsupportedPlatformRejection:

    def test_ios_is_rejected(self, resolver):
        with pytest.raises((ValueError, NotImplementedError, RuntimeError)):
            resolver.resolve("iOS", "2022.3.45f1", "ghcr.io/test")

    def test_ios_error_mentions_ios(self, resolver):
        with pytest.raises(Exception) as exc_info:
            resolver.resolve("iOS", "2022.3.45f1", "ghcr.io/test")
        msg = str(exc_info.value).lower()
        assert "ios" in msg, f"iOS error should mention iOS: {exc_info.value}"

    def test_windows64_is_rejected(self, resolver):
        with pytest.raises((ValueError, NotImplementedError, RuntimeError)):
            resolver.resolve("Windows64", "2022.3.45f1", "ghcr.io/test")

    def test_windows64_error_mentions_windows(self, resolver):
        with pytest.raises(Exception) as exc_info:
            resolver.resolve("Windows64", "2022.3.45f1", "ghcr.io/test")
        msg = str(exc_info.value).lower()
        assert "windows" in msg, f"Windows64 error should mention Windows: {exc_info.value}"

    def test_unknown_platform_is_rejected(self, resolver):
        with pytest.raises((ValueError, KeyError, RuntimeError)):
            resolver.resolve("PS5", "2022.3.45f1", "ghcr.io/test")

    def test_empty_platform_is_rejected(self, resolver):
        with pytest.raises((ValueError, KeyError, RuntimeError, TypeError)):
            resolver.resolve("", "2022.3.45f1", "ghcr.io/test")


# ---------------------------------------------------------------------------
# Release mode — digest-pinned requirement
# ---------------------------------------------------------------------------

class TestReleaseModeDigestPin:

    def test_release_mode_without_digest_raises(self, resolver):
        """release_mode=True with no digest → should raise."""
        with pytest.raises((ValueError, RuntimeError)):
            resolver.resolve(
                "Android",
                "2022.3.45f1",
                "ghcr.io/test",
                release_mode=True,
                # No image_digest provided
            )

    def test_release_mode_with_digest_succeeds(self, resolver):
        digest = "sha256:" + "a" * 64
        result = resolver.resolve(
            "Android",
            "2022.3.45f1",
            "ghcr.io/test",
            image_digest=digest,
            release_mode=True,
        )
        assert "@sha256:" in result["image_ref"], \
            "Release mode must produce a digest-pinned image reference"

    def test_release_mode_result_contains_digest(self, resolver):
        digest = "sha256:" + "a" * 64
        result = resolver.resolve(
            "Android",
            "2022.3.45f1",
            "ghcr.io/test",
            image_digest=digest,
            release_mode=True,
        )
        assert digest in result["image_ref"] or result["digest"] == digest


# ---------------------------------------------------------------------------
# enforce_immutable_reference
# ---------------------------------------------------------------------------

class TestEnforceImmutableReference:

    def test_non_release_mode_passes_mutable_ref(self, resolver):
        ref = resolver.enforce_immutable_reference(
            "ghcr.io/test/unity:latest", None, release_mode=False
        )
        assert ref == "ghcr.io/test/unity:latest"

    def test_release_mode_with_digest_in_ref_passes(self, resolver):
        digest = "sha256:" + "a" * 64
        ref_with_digest = f"ghcr.io/test/unity:2022.3.45f1-android@{digest}"
        result = resolver.enforce_immutable_reference(
            ref_with_digest, None, release_mode=True
        )
        assert result == ref_with_digest

    def test_release_mode_appends_separate_digest(self, resolver):
        digest = "sha256:" + "a" * 64
        result = resolver.enforce_immutable_reference(
            "ghcr.io/test/unity:2022.3.45f1-android",
            digest,
            release_mode=True,
        )
        assert "@sha256:" in result or digest in result

    def test_release_mode_latest_tag_rejected(self, resolver):
        with pytest.raises(ValueError) as exc_info:
            resolver.enforce_immutable_reference(
                "ghcr.io/test/unity:latest", None, release_mode=True
            )
        msg = str(exc_info.value).lower()
        assert any(kw in msg for kw in ("mutable", "digest", "immutable", "latest")), \
            f"Error should explain mutable tag rejection: {exc_info.value}"

    def test_release_mode_edge_tag_rejected(self, resolver):
        with pytest.raises(ValueError):
            resolver.enforce_immutable_reference(
                "ghcr.io/test/unity:edge", None, release_mode=True
            )

    def test_release_mode_main_tag_rejected(self, resolver):
        with pytest.raises(ValueError):
            resolver.enforce_immutable_reference(
                "ghcr.io/test/unity:main", None, release_mode=True
            )

    def test_release_mode_no_ref_no_digest_raises(self, resolver):
        with pytest.raises(ValueError):
            resolver.enforce_immutable_reference(
                "ghcr.io/test/unity:2022.3.45f1-android",
                None,
                release_mode=True,
            )


# ---------------------------------------------------------------------------
# validate_contract_version
# ---------------------------------------------------------------------------

class TestValidateContractVersion:

    def test_version_1_accepted(self, resolver):
        manifest = {"image_contract_version": "1"}
        resolver.validate_contract_version(manifest)  # Must not raise

    def test_missing_version_defaults_to_1(self, resolver):
        manifest = {}
        resolver.validate_contract_version(manifest)  # Must not raise (defaults to "1")

    def test_future_version_accepted_or_warns(self, resolver):
        """Future minor versions should be accepted (forward compatibility)."""
        manifest = {"image_contract_version": "2"}
        try:
            resolver.validate_contract_version(manifest)
        except ValueError:
            pass  # Rejection is also acceptable for major version jumps

    def test_non_integer_version_raises(self, resolver):
        manifest = {"image_contract_version": "not-a-number"}
        with pytest.raises(ValueError):
            resolver.validate_contract_version(manifest)


# ---------------------------------------------------------------------------
# Manifest file loading (load_manifest_from_file)
# ---------------------------------------------------------------------------

class TestManifestFileLoading:

    def test_load_valid_manifest(self, resolver, manifest_file):
        manifest = resolver.load_manifest_from_file(manifest_file)
        assert isinstance(manifest, dict)
        assert "images" in manifest

    def test_missing_manifest_raises_file_not_found(self, resolver, tmp_path):
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            resolver.load_manifest_from_file(missing)

    def test_invalid_json_raises_value_error(self, resolver, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{not valid json")
        with pytest.raises(ValueError):
            resolver.load_manifest_from_file(bad_json)

    def test_manifest_used_in_resolve(self, resolver, manifest_file):
        result = resolver.resolve(
            "Android",
            "2022.3.45f1",
            "ghcr.io/test",
            manifest_path=manifest_file,
        )
        assert "@sha256:" in result["image_ref"] or result["digest"] != "", \
            "Digest from manifest should be used when manifest file is provided"

    def test_manifest_digest_used_for_android(self, resolver, manifest_file):
        result = resolver.resolve(
            "Android",
            "2022.3.45f1",
            "ghcr.io/test",
            manifest_path=manifest_file,
        )
        expected_digest = "sha256:" + "a" * 64
        assert result.get("digest") == expected_digest or expected_digest in result["image_ref"]

    def test_unity_version_mismatch_in_manifest_raises(self, resolver, tmp_path):
        """If manifest specifies a different Unity version, resolve() must raise."""
        manifest = _make_resolve_manifest(unity_version="2022.3.45f1")
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(manifest))
        with pytest.raises(ValueError) as exc_info:
            resolver.resolve(
                "Android",
                "6000.0.0f1",   # Different version
                "ghcr.io/test",
                manifest_path=path,
            )
        msg = str(exc_info.value).lower()
        assert "version" in msg or "mismatch" in msg, \
            f"Error should mention version mismatch: {exc_info.value}"
