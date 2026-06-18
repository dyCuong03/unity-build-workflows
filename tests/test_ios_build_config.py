"""
Tests for iOS BuildConfig JSON schema validation.

Validates that:
- Well-formed iOS configs pass schema validation
- Invalid bundle identifiers are rejected
- Contract-required iOS fields are honoured by the schema
- Export method enum, signingStyle enum, architecture enum are enforced

PENDING TEAMMATE: The `ios` schema section is being extended by the
architect-resolver teammate to add new contract fields:
  marketingVersion, sdkVersion, architecture, xcodeVersion,
  developmentTeamId, signingStyle, provisioningProfileSpecifier,
  codeSignIdentity, enableBitcode, generateSymbols, uploadSymbols,
  uploadToTestFlight.

All fields are validated against schemas/unity-build-config.schema.json.
The architect-resolver teammate confirmed the schema is complete (v2.1.0).
"""
import copy
import json

import jsonschema
import pytest


# ---------------------------------------------------------------------------
# Helpers (mirrors test_build_config.py style)
# ---------------------------------------------------------------------------

def _validate(config: dict, validator) -> list:
    return list(validator.iter_errors(config))


def _assert_valid(config: dict, validator):
    errors = _validate(config, validator)
    assert errors == [], "\n".join(e.message for e in errors)


def _assert_invalid(config: dict, validator):
    errors = _validate(config, validator)
    assert errors, "Expected schema validation to fail, but it passed."


def _base_config(**ios_fields) -> dict:
    """Return a minimal valid config with an iOS section."""
    c = {
        "projectName": "ios-game",
        "companyName": "Acme",
        "productName": "iOS Game",
        "bundleVersion": "1.0.0",
        "outputDirectory": "Builds/iOS",
        "scenes": ["Assets/Scenes/Main.unity"],
    }
    if ios_fields:
        c["iOS"] = ios_fields  # "iOS" is the canonical key; "ios" is deprecated-but-accepted
    return c


# ---------------------------------------------------------------------------
# Valid iOS configs
# ---------------------------------------------------------------------------

class TestValidIOSConfigs:

    def test_valid_ios_config_fixture_passes(self, schema_validator):
        """Full contract iOS config from fixture must pass schema."""
        from pathlib import Path
        import json
        fixture = Path(__file__).parent / "fixtures" / "valid_ios_config.json"
        assert fixture.exists(), f"Fixture missing: {fixture}"
        config = json.loads(fixture.read_text())
        # Remove $schema key before validating (validator uses its own ref)
        config.pop("$schema", None)
        _assert_valid(config, schema_validator)

    def test_valid_ios_minimal_fixture_passes(self, schema_validator):
        """Minimal iOS config (bundleIdentifier only) must pass schema."""
        from pathlib import Path
        import json
        fixture = Path(__file__).parent / "fixtures" / "valid_ios_minimal.json"
        assert fixture.exists(), f"Fixture missing: {fixture}"
        config = json.loads(fixture.read_text())
        config.pop("$schema", None)
        _assert_valid(config, schema_validator)

    def test_ios_bundle_identifier_two_segments_passes(self, schema_validator):
        config = _base_config(bundleIdentifier="com.example.game")
        _assert_valid(config, schema_validator)

    def test_ios_bundle_identifier_three_segments_passes(self, schema_validator):
        config = _base_config(bundleIdentifier="com.example.game")
        _assert_valid(config, schema_validator)

    def test_ios_bundle_identifier_with_hyphens_passes(self, schema_validator):
        config = _base_config(bundleIdentifier="com.buzz-studio.my-game")
        _assert_valid(config, schema_validator)

    def test_ios_bundle_identifier_with_numbers_passes(self, schema_validator):
        config = _base_config(bundleIdentifier="com.studio2.game3")
        _assert_valid(config, schema_validator)

    def test_ios_export_method_app_store_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            exportMethod="app-store",
        )
        _assert_valid(config, schema_validator)

    def test_ios_export_method_ad_hoc_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            exportMethod="ad-hoc",
        )
        _assert_valid(config, schema_validator)

    def test_ios_export_method_development_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            exportMethod="development",
        )
        _assert_valid(config, schema_validator)

    def test_ios_export_method_enterprise_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            exportMethod="enterprise",
        )
        _assert_valid(config, schema_validator)

    def test_ios_target_os_version_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            targetOSVersion="16.0",
        )
        _assert_valid(config, schema_validator)

    def test_ios_build_number_string_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            buildNumber="123",
        )
        _assert_valid(config, schema_validator)


# ---------------------------------------------------------------------------
# Invalid bundle identifiers
# ---------------------------------------------------------------------------

class TestInvalidIOSBundleIdentifier:

    def test_invalid_ios_bundle_id_fixture_fails(self, schema_validator):
        """Fixture with leading-digit bundle ID must fail."""
        from pathlib import Path
        import json
        fixture = Path(__file__).parent / "fixtures" / "invalid_ios_bundle_id.json"
        assert fixture.exists(), f"Fixture missing: {fixture}"
        config = json.loads(fixture.read_text())
        config.pop("$schema", None)
        _assert_invalid(config, schema_validator)

    def test_single_segment_bundle_id_fails(self, schema_validator):
        """Single-segment bundle IDs are not valid reverse-DNS."""
        config = _base_config(bundleIdentifier="mygame")
        _assert_invalid(config, schema_validator)

    def test_leading_digit_segment_fails(self, schema_validator):
        config = _base_config(bundleIdentifier="123.example.game")
        _assert_invalid(config, schema_validator)

    def test_segment_starting_with_digit_fails(self, schema_validator):
        config = _base_config(bundleIdentifier="com.123studio.game")
        _assert_invalid(config, schema_validator)

    def test_empty_bundle_id_fails(self, schema_validator):
        config = _base_config(bundleIdentifier="")
        _assert_invalid(config, schema_validator)

    def test_bundle_id_with_spaces_fails(self, schema_validator):
        config = _base_config(bundleIdentifier="com.my studio.game")
        _assert_invalid(config, schema_validator)

    def test_bundle_id_with_underscore_in_wrong_position(self, schema_validator):
        """Underscore-only segment identifiers are disallowed (must start with letter)."""
        config = _base_config(bundleIdentifier="com._studio.game")
        _assert_invalid(config, schema_validator)


# ---------------------------------------------------------------------------
# Invalid export method
# ---------------------------------------------------------------------------

class TestInvalidIOSExportMethod:

    def test_invalid_export_method_rejected(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            exportMethod="testflight",  # Not a valid enum value
        )
        _assert_invalid(config, schema_validator)

    def test_random_export_method_rejected(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            exportMethod="magic-upload",
        )
        _assert_invalid(config, schema_validator)


# ---------------------------------------------------------------------------
# Invalid targetOSVersion
# ---------------------------------------------------------------------------

class TestInvalidTargetOSVersion:

    def test_target_os_missing_minor_fails(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            targetOSVersion="16",  # Missing .x
        )
        _assert_invalid(config, schema_validator)

    def test_target_os_three_segments_fails(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            targetOSVersion="16.0.1",  # Too many segments
        )
        _assert_invalid(config, schema_validator)


# ---------------------------------------------------------------------------
# Invalid buildNumber
# ---------------------------------------------------------------------------

class TestInvalidIOSBuildNumber:

    def test_non_numeric_build_number_fails(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            buildNumber="1.0.0",  # Must be all digits
        )
        _assert_invalid(config, schema_validator)

    def test_build_number_with_letters_fails(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            buildNumber="42a",
        )
        _assert_invalid(config, schema_validator)


# ---------------------------------------------------------------------------
# Contract fields — new fields expected in updated schema
# Schema confirmed complete — all fields present in v2.1.0 schema.
# ---------------------------------------------------------------------------

class TestIOSContractFields:
    """
    These tests verify that the schema accepts the full iOS contract field set defined
    in the v2.1.0 contract. All fields confirmed present in
    schemas/unity-build-config.schema.json by architect-resolver (xfail markers removed).
    """

    def test_signing_style_manual_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            signingStyle="manual",
        )
        _assert_valid(config, schema_validator)

    def test_signing_style_automatic_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            signingStyle="automatic",
        )
        _assert_valid(config, schema_validator)

    def test_invalid_signing_style_rejected(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            signingStyle="enterprise-magic",
        )
        _assert_invalid(config, schema_validator)

    def test_development_team_id_ten_chars_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            developmentTeamId="ABCDE12345",
        )
        _assert_valid(config, schema_validator)

    def test_development_team_id_wrong_length_fails(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            developmentTeamId="SHORT",
        )
        _assert_invalid(config, schema_validator)

    def test_xcode_version_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            xcodeVersion="15.2",
        )
        _assert_valid(config, schema_validator)

    def test_marketing_version_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            marketingVersion="1.0.0",
        )
        _assert_valid(config, schema_validator)

    def test_sdk_version_iphoneos_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            sdkVersion="iphoneos",
        )
        _assert_valid(config, schema_validator)

    def test_invalid_sdk_version_fails(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            sdkVersion="windowsphone",
        )
        _assert_invalid(config, schema_validator)

    def test_ios_architecture_arm64_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            architecture="ARM64",
        )
        _assert_valid(config, schema_validator)

    def test_ios_architecture_invalid_fails(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            architecture="x86",  # Not valid for iOS
        )
        _assert_invalid(config, schema_validator)

    def test_upload_to_test_flight_bool_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            uploadToTestFlight=True,
        )
        _assert_valid(config, schema_validator)

    def test_enable_bitcode_false_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            enableBitcode=False,
        )
        _assert_valid(config, schema_validator)

    def test_generate_symbols_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            generateSymbols=True,
        )
        _assert_valid(config, schema_validator)

    def test_upload_symbols_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            uploadSymbols=True,
        )
        _assert_valid(config, schema_validator)

    def test_provisioning_profile_specifier_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            provisioningProfileSpecifier="MyApp Distribution",
        )
        _assert_valid(config, schema_validator)

    def test_code_sign_identity_passes(self, schema_validator):
        config = _base_config(
            bundleIdentifier="com.example.game",
            codeSignIdentity="iPhone Distribution",
        )
        _assert_valid(config, schema_validator)


# ---------------------------------------------------------------------------
# iOS config does not pollute other platforms
# ---------------------------------------------------------------------------

class TestIOSIsolation:

    def test_ios_section_does_not_affect_android_validation(self, schema_validator):
        """Adding an iOS section must not invalidate a config that also has android."""
        config = {
            "projectName": "cross-platform",
            "companyName": "Acme",
            "productName": "Cross Platform",
            "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "android": {"applicationId": "com.example.game"},
            "iOS": {"bundleIdentifier": "com.example.game"},  # canonical key
        }
        _assert_valid(config, schema_validator)

    def test_ios_config_without_android_passes(self, schema_validator):
        config = _base_config(bundleIdentifier="com.example.game")
        _assert_valid(config, schema_validator)

    def test_deprecated_lowercase_ios_key_still_accepted(self, schema_validator):
        """
        Backward-compat contract: lowercase 'ios' key is deprecated but must still pass schema.
        Canonical key is 'iOS'. The schema $refs both to the same definition.
        This test must pass until 'ios' is removed in v3.0.0.
        """
        config = {
            "projectName": "ios-game",
            "companyName": "Acme",
            "productName": "iOS Game",
            "bundleVersion": "1.0.0",
            "outputDirectory": "Builds/iOS",
            "scenes": ["Assets/Scenes/Main.unity"],
            "ios": {"bundleIdentifier": "com.example.game"},  # deprecated lowercase key
        }
        _assert_valid(config, schema_validator)
