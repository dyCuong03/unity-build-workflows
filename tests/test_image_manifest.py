"""
Tests for Docker image manifest schema validation.

Uses the JSON Schema at docker/metadata/image-manifest.schema.json to validate
per-image manifest documents (embedded in image labels as org.unity.build.manifest).

Covers:
- Valid manifest passes schema validation
- Missing required fields rejected
- Invalid Unity version format rejected
- Mutable image reference (no digest) — schema allows it but mutable detection is a separate concern
- Supported targets list validated against allowed enum values
- Schema version format (MAJOR.MINOR.PATCH)
- Digest format validation (sha256:<64 hex chars>)
- Android variant requires androidSdkVersion, androidNdkVersion, jdkVersion
- contractVersion must be a positive integer
"""
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"
MANIFEST_SCHEMA_PATH = REPO_ROOT / "docker" / "metadata" / "image-manifest.schema.json"


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def manifest_schema():
    assert MANIFEST_SCHEMA_PATH.exists(), \
        f"Manifest schema not found: {MANIFEST_SCHEMA_PATH}"
    with MANIFEST_SCHEMA_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def manifest_validator(manifest_schema):
    try:
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
        resource = Resource.from_contents(manifest_schema)
        registry = Registry().with_resource(MANIFEST_SCHEMA_PATH.as_uri(), resource)
        return Draft7Validator(manifest_schema, registry=registry)
    except (ImportError, TypeError):
        resolver = jsonschema.RefResolver(
            base_uri=MANIFEST_SCHEMA_PATH.as_uri(),
            referrer=manifest_schema,
        )
        return jsonschema.Draft7Validator(manifest_schema, resolver=resolver)


def _validate(manifest: dict, validator) -> list:
    return list(validator.iter_errors(manifest))


def _assert_valid(manifest: dict, validator):
    errors = _validate(manifest, validator)
    assert not errors, "\n".join(e.message for e in errors)


def _assert_invalid(manifest: dict, validator):
    errors = _validate(manifest, validator)
    assert errors, "Expected schema validation to fail, but it passed."


# ---------------------------------------------------------------------------
# Minimal valid manifest builder
# ---------------------------------------------------------------------------

def _make_valid_manifest(**overrides) -> dict:
    base = {
        "schemaVersion": "1.0.0",
        "contractVersion": 1,
        "imageReference": "ghcr.io/example-namespace/unity-webgl:2022.3.45f1",
        "unityVersion": "2022.3.45f1",
        "variant": "webgl",
        "buildTimestamp": "2026-06-12T10:00:00Z",
    }
    base.update(overrides)
    return base


def _make_valid_android_manifest(**overrides) -> dict:
    base = _make_valid_manifest(
        variant="android",
        imageReference="ghcr.io/example-namespace/unity-android:2022.3.45f1",
        androidSdkVersion=34,
        androidNdkVersion="r23b",
        jdkVersion="17.0.9",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Valid manifests
# ---------------------------------------------------------------------------

class TestValidManifest:

    def test_fixture_passes_schema(self, manifest_validator):
        with (FIXTURES_DIR / "valid_image_manifest.json").open() as f:
            data = json.load(f)
        _assert_valid(data, manifest_validator)

    def test_minimal_webgl_manifest_passes(self, manifest_validator):
        _assert_valid(_make_valid_manifest(), manifest_validator)

    def test_minimal_android_manifest_passes(self, manifest_validator):
        _assert_valid(_make_valid_android_manifest(), manifest_validator)

    def test_linux_variant_passes(self, manifest_validator):
        manifest = _make_valid_manifest(
            variant="linux-il2cpp",
            imageReference="ghcr.io/example-namespace/unity-linux:2022.3.45f1",
            supportedTargets=["StandaloneLinux64", "LinuxServer"],
        )
        _assert_valid(manifest, manifest_validator)

    def test_base_variant_passes(self, manifest_validator):
        manifest = _make_valid_manifest(
            variant="base",
            imageReference="ghcr.io/example-namespace/unity-base:2022.3.45f1",
        )
        _assert_valid(manifest, manifest_validator)

    def test_optional_fields_allowed(self, manifest_validator):
        manifest = _make_valid_manifest(
            imageDigest="sha256:" + "a" * 64,
            modules=["webgl"],
            osVersion="Ubuntu 22.04.4 LTS",
            toolingVersion="1.0.0",
            sourceCommit="5bd161f",
            supportedTargets=["WebGL"],
            supportedScriptingBackends=["IL2CPP", "Mono"],
        )
        _assert_valid(manifest, manifest_validator)


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

class TestMissingRequiredFields:

    @pytest.mark.parametrize("field", [
        "schemaVersion",
        "contractVersion",
        "imageReference",
        "unityVersion",
        "variant",
        "buildTimestamp",
    ])
    def test_missing_required_field_fails(self, manifest_validator, field):
        manifest = _make_valid_manifest()
        del manifest[field]
        _assert_invalid(manifest, manifest_validator)

    def test_missing_fields_fixture_fails(self, manifest_validator):
        with (FIXTURES_DIR / "invalid_image_manifest_missing_fields.json").open() as f:
            data = json.load(f)
        _assert_invalid(data, manifest_validator)


# ---------------------------------------------------------------------------
# Unity version format
# ---------------------------------------------------------------------------

class TestUnityVersionFormat:

    @pytest.mark.parametrize("bad_version", [
        "latest",
        "2022.3",
        "2022",
        "not-a-version",
        "",
        "2022.3.45",      # missing changeset designator
        "2022.3.45-f1",   # hyphen instead of direct suffix
    ])
    def test_invalid_unity_version_rejected(self, manifest_validator, bad_version):
        manifest = _make_valid_manifest(unityVersion=bad_version)
        _assert_invalid(manifest, manifest_validator)

    @pytest.mark.parametrize("good_version", [
        "2022.3.45f1",
        "6000.0.0f1",
        "2021.3.16f1",
        "2023.1.0a1",
        "2022.3.5b2",
    ])
    def test_valid_unity_version_accepted(self, manifest_validator, good_version):
        manifest = _make_valid_manifest(unityVersion=good_version)
        _assert_valid(manifest, manifest_validator)


# ---------------------------------------------------------------------------
# Variant enum
# ---------------------------------------------------------------------------

class TestVariantEnum:

    @pytest.mark.parametrize("valid_variant", [
        "base", "android", "webgl", "linux-il2cpp", "ios"
    ])
    def test_valid_variant_accepted(self, manifest_validator, valid_variant):
        if valid_variant == "android":
            manifest = _make_valid_android_manifest()
        else:
            manifest = _make_valid_manifest(
                variant=valid_variant,
                imageReference=f"ghcr.io/test/unity-{valid_variant}:2022.3.45f1",
            )
        _assert_valid(manifest, manifest_validator)

    @pytest.mark.parametrize("bad_variant", [
        "ps5", "xbox", "iOS", "Windows", "unknown", ""
    ])
    def test_invalid_variant_rejected(self, manifest_validator, bad_variant):
        manifest = _make_valid_manifest(variant=bad_variant)
        _assert_invalid(manifest, manifest_validator)


# ---------------------------------------------------------------------------
# Supported targets enum
# ---------------------------------------------------------------------------

class TestSupportedTargets:

    @pytest.mark.parametrize("target", [
        "Android", "iOS", "WebGL",
        "StandaloneLinux64", "LinuxServer",
        "StandaloneWindows64", "StandaloneOSX",
    ])
    def test_each_valid_target_accepted(self, manifest_validator, target):
        manifest = _make_valid_manifest(supportedTargets=[target])
        _assert_valid(manifest, manifest_validator)

    def test_invalid_target_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(supportedTargets=["PS5"])
        _assert_invalid(manifest, manifest_validator)

    def test_multiple_valid_targets_accepted(self, manifest_validator):
        manifest = _make_valid_manifest(
            supportedTargets=["StandaloneLinux64", "LinuxServer"]
        )
        _assert_valid(manifest, manifest_validator)


# ---------------------------------------------------------------------------
# Schema version format (MAJOR.MINOR.PATCH)
# ---------------------------------------------------------------------------

class TestSchemaVersionFormat:

    @pytest.mark.parametrize("bad_schema_version", [
        "1", "1.0", "v1.0.0", "latest", ""
    ])
    def test_invalid_schema_version_rejected(self, manifest_validator, bad_schema_version):
        manifest = _make_valid_manifest(schemaVersion=bad_schema_version)
        _assert_invalid(manifest, manifest_validator)

    @pytest.mark.parametrize("good_schema_version", [
        "1.0.0", "2.1.3", "10.0.0"
    ])
    def test_valid_schema_version_accepted(self, manifest_validator, good_schema_version):
        manifest = _make_valid_manifest(schemaVersion=good_schema_version)
        _assert_valid(manifest, manifest_validator)


# ---------------------------------------------------------------------------
# Digest format (sha256:<64 hex chars>)
# ---------------------------------------------------------------------------

class TestDigestFormat:

    def test_valid_digest_accepted(self, manifest_validator):
        manifest = _make_valid_manifest(imageDigest="sha256:" + "a" * 64)
        _assert_valid(manifest, manifest_validator)

    def test_short_digest_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(imageDigest="sha256:" + "a" * 32)
        _assert_invalid(manifest, manifest_validator)

    def test_long_digest_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(imageDigest="sha256:" + "a" * 65)
        _assert_invalid(manifest, manifest_validator)

    def test_missing_sha256_prefix_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(imageDigest="a" * 64)
        _assert_invalid(manifest, manifest_validator)

    def test_md5_digest_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(imageDigest="md5:abc123")
        _assert_invalid(manifest, manifest_validator)

    def test_uppercase_hex_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(imageDigest="sha256:" + "A" * 64)
        _assert_invalid(manifest, manifest_validator)


# ---------------------------------------------------------------------------
# contractVersion must be a positive integer
# ---------------------------------------------------------------------------

class TestContractVersion:

    def test_contract_version_1_accepted(self, manifest_validator):
        manifest = _make_valid_manifest(contractVersion=1)
        _assert_valid(manifest, manifest_validator)

    def test_contract_version_2_accepted(self, manifest_validator):
        manifest = _make_valid_manifest(contractVersion=2)
        _assert_valid(manifest, manifest_validator)

    def test_contract_version_0_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(contractVersion=0)
        _assert_invalid(manifest, manifest_validator)

    def test_contract_version_negative_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(contractVersion=-1)
        _assert_invalid(manifest, manifest_validator)

    def test_contract_version_string_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(contractVersion="1")
        _assert_invalid(manifest, manifest_validator)


# ---------------------------------------------------------------------------
# Android variant requires extra fields
# ---------------------------------------------------------------------------

class TestAndroidVariantRequirements:

    def test_android_without_sdk_version_rejected(self, manifest_validator):
        manifest = _make_valid_android_manifest()
        del manifest["androidSdkVersion"]
        _assert_invalid(manifest, manifest_validator)

    def test_android_without_ndk_version_rejected(self, manifest_validator):
        manifest = _make_valid_android_manifest()
        del manifest["androidNdkVersion"]
        _assert_invalid(manifest, manifest_validator)

    def test_android_without_jdk_version_rejected(self, manifest_validator):
        manifest = _make_valid_android_manifest()
        del manifest["jdkVersion"]
        _assert_invalid(manifest, manifest_validator)

    def test_webgl_without_android_fields_passes(self, manifest_validator):
        manifest = _make_valid_manifest(
            variant="webgl",
            imageReference="ghcr.io/test/unity-webgl:2022.3.45f1",
        )
        _assert_valid(manifest, manifest_validator)

    def test_android_sdk_version_must_be_positive(self, manifest_validator):
        manifest = _make_valid_android_manifest(androidSdkVersion=0)
        _assert_invalid(manifest, manifest_validator)


# ---------------------------------------------------------------------------
# Additional properties rejected
# ---------------------------------------------------------------------------

class TestAdditionalPropertiesRejected:

    def test_unknown_field_rejected(self, manifest_validator):
        manifest = _make_valid_manifest(unknownField="should_fail")
        _assert_invalid(manifest, manifest_validator)

    def test_multiple_unknown_fields_rejected(self, manifest_validator):
        manifest = _make_valid_manifest()
        manifest["foo"] = "bar"
        manifest["baz"] = 42
        _assert_invalid(manifest, manifest_validator)
