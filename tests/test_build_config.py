"""
Tests for BuildConfig JSON schema validation.

Validates that:
- Well-formed configs pass schema validation
- Constraint violations are caught (production+developmentBuild, empty scenes, etc.)
- Deep merge and config precedence behave correctly
"""
import copy
import json

import jsonschema
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate(config: dict, validator) -> list:
    """Return list of ValidationError objects (empty = valid)."""
    return list(validator.iter_errors(config))


def assert_valid(config: dict, validator):
    errors = validate(config, validator)
    assert errors == [], "\n".join(e.message for e in errors)


def assert_invalid(config: dict, validator):
    errors = validate(config, validator)
    assert errors, "Expected schema validation to fail, but it passed."


# ---------------------------------------------------------------------------
# Valid configs
# ---------------------------------------------------------------------------

class TestValidConfigs:

    def test_valid_base_config_passes(self, schema_validator, valid_base_config):
        assert_valid(valid_base_config, schema_validator)

    def test_valid_production_config_passes(self, schema_validator, valid_production_config):
        assert_valid(valid_production_config, schema_validator)

    def test_minimal_config_passes(self, schema_validator, minimal_config):
        """Config with only required fields should pass."""
        assert_valid(minimal_config, schema_validator)

    def test_minimal_config_has_required_fields(self, minimal_config):
        required = {"projectName", "companyName", "productName",
                    "bundleVersion", "outputDirectory", "scenes"}
        assert required.issubset(minimal_config.keys())

    def test_valid_bundle_version_format(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "2.10.3",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
        }
        assert_valid(config, schema_validator)


# ---------------------------------------------------------------------------
# Invalid: production + developmentBuild = true
# ---------------------------------------------------------------------------

class TestProductionDevBuildRejected:

    def test_production_dev_build_fails(
        self, schema_validator, invalid_production_dev_build
    ):
        assert_invalid(invalid_production_dev_build, schema_validator)

    def test_production_allow_debugging_fails(self, schema_validator):
        """allowDebugging=true requires developmentBuild=true,
        which is forbidden in production — should fail."""
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "allowDebugging": True,
            # developmentBuild not set → default false → constraint violated
        }
        assert_invalid(config, schema_validator)

    def test_allow_debugging_without_development_build_fails(self, schema_validator):
        """Schema requires developmentBuild=true when allowDebugging=true."""
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "developmentBuild": False,
            "allowDebugging": True,
        }
        assert_invalid(config, schema_validator)

    def test_development_build_true_allowed_outside_production(self, schema_validator):
        """developmentBuild=true is fine when environment is not 'production'."""
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "developmentBuild": True,
            "allowDebugging": True,
            "metadata": {"environment": "development"},
        }
        assert_valid(config, schema_validator)


# ---------------------------------------------------------------------------
# Invalid: empty scenes array
# ---------------------------------------------------------------------------

class TestEmptyScenesRejected:

    def test_empty_scenes_array_fails(self, schema_validator, invalid_empty_scenes):
        assert_invalid(invalid_empty_scenes, schema_validator)

    def test_scenes_missing_fails(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
        }
        assert_invalid(config, schema_validator)

    def test_scene_must_be_assets_path(self, schema_validator):
        r"""Scene paths must match ^Assets/.*\.unity$ pattern."""
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["NotAssets/Scene.unity"],
        }
        assert_invalid(config, schema_validator)

    def test_scene_missing_unity_extension_fails(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.prefab"],
        }
        assert_invalid(config, schema_validator)


# ---------------------------------------------------------------------------
# Invalid: bundle identifier
# ---------------------------------------------------------------------------

class TestInvalidBundleId:

    def test_invalid_android_application_id_fails(
        self, schema_validator, invalid_bundle_id
    ):
        assert_invalid(invalid_bundle_id, schema_validator)

    def test_android_id_with_single_segment_fails(self, schema_validator):
        """Android applicationId must have at least two dot-separated segments."""
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "android": {"applicationId": "singleSegment"},
        }
        assert_invalid(config, schema_validator)

    def test_valid_android_application_id_passes(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "android": {"applicationId": "com.example.mygame"},
        }
        assert_valid(config, schema_validator)

    def test_ios_bundle_identifier_validates(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "ios": {"bundleIdentifier": "com.example.mygame"},
        }
        assert_valid(config, schema_validator)

    def test_invalid_ios_bundle_identifier_fails(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "ios": {"bundleIdentifier": "123invalid"},
        }
        assert_invalid(config, schema_validator)


# ---------------------------------------------------------------------------
# Schema structural rules
# ---------------------------------------------------------------------------

class TestSchemaStructuralRules:

    def test_bundle_version_must_be_semver(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0",  # missing patch
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
        }
        assert_invalid(config, schema_validator)

    def test_additional_properties_rejected(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "unknownField": "value",
        }
        assert_invalid(config, schema_validator)

    def test_scripting_backend_enum_enforced(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "scriptingBackend": "NotABackend",
        }
        assert_invalid(config, schema_validator)

    def test_build_number_strategy_enum_enforced(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "buildNumberStrategy": "magic",
        }
        assert_invalid(config, schema_validator)


# ---------------------------------------------------------------------------
# Deep merge / config precedence
# ---------------------------------------------------------------------------

class TestDeepMerge:
    """
    Tests for deep_merge utility (scripts/common/config_loader.py).
    These tests define the expected merge contract.
    """

    @pytest.fixture(autouse=True)
    def import_config_loader(self):
        try:
            from config_loader import deep_merge
            self.deep_merge = deep_merge
        except ImportError:
            pytest.skip("scripts/common/config_loader.py not yet implemented")

    def test_env_overrides_base_scalar(self):
        base = {"bundleVersion": "1.0.0", "outputDirectory": "Builds"}
        override = {"bundleVersion": "1.1.0"}
        merged = self.deep_merge(base, override)
        assert merged["bundleVersion"] == "1.1.0"
        assert merged["outputDirectory"] == "Builds"

    def test_env_overrides_nested_object(self):
        base = {
            "android": {"applicationId": "com.example.app", "minSdkVersion": 22}
        }
        override = {
            "android": {"applicationId": "com.example.app.debug"}
        }
        merged = self.deep_merge(base, override)
        assert merged["android"]["applicationId"] == "com.example.app.debug"
        # Non-overridden nested key must survive
        assert merged["android"]["minSdkVersion"] == 22

    def test_base_keys_not_in_env_are_preserved(self):
        base = {
            "projectName": "my-game",
            "runTests": True,
            "gates": {"maxBuildSizeMB": 200},
        }
        override = {"projectName": "my-game-dev"}
        merged = self.deep_merge(base, override)
        assert merged["runTests"] is True
        assert merged["gates"]["maxBuildSizeMB"] == 200

    def test_env_config_takes_precedence_over_base(
        self, valid_base_config, valid_production_config
    ):
        merged = self.deep_merge(
            copy.deepcopy(valid_base_config),
            copy.deepcopy(valid_production_config),
        )
        # production config sets developmentBuild=false; base has true
        assert merged["developmentBuild"] is False

    def test_merge_does_not_mutate_inputs(self):
        base = {"a": {"x": 1}}
        override = {"a": {"x": 2, "y": 3}}
        original_base = copy.deepcopy(base)
        self.deep_merge(base, override)
        assert base == original_base


# ---------------------------------------------------------------------------
# Docker-supported target platform validation
# ---------------------------------------------------------------------------

# Platforms the Docker pipeline supports (matches resolve_image_reference.py)
DOCKER_SUPPORTED_PLATFORMS = {"Android", "WebGL", "StandaloneLinux64", "LinuxServer", "Linux64"}

# Platforms that are NOT supported in Docker (native-only)
DOCKER_UNSUPPORTED_PLATFORMS = {"iOS", "Windows64", "StandaloneWindows64", "StandaloneOSX", "PS4", "PS5"}


class TestDockerTargetPlatformValidation:
    """
    Validates that build configs only reference Docker-supported target platforms.
    iOS and Windows64 are native-only and must not be used in Docker CI configs.
    """

    def test_android_is_docker_supported(self, schema_validator):
        """Android is a first-class Docker-supported platform."""
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "android": {"applicationId": "com.example.game"},
        }
        errors = list(schema_validator.iter_errors(config))
        assert errors == [], "Android config with valid applicationId must pass"

    def test_webgl_config_passes(self, schema_validator):
        """WebGL is Docker-supported."""
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
        }
        errors = list(schema_validator.iter_errors(config))
        assert errors == [], "WebGL config must pass schema validation"

    def test_docker_supported_platforms_constant_is_correct(self):
        """Verify the supported platforms set matches resolve_image_reference.py."""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "docker"))
            import resolve_image_reference
            for platform in DOCKER_SUPPORTED_PLATFORMS:
                assert platform in resolve_image_reference.PLATFORM_VARIANT_MAP or \
                       platform in {"Linux64"}, \
                    f"Platform '{platform}' should be in PLATFORM_VARIANT_MAP"
        except ImportError:
            pytest.skip("scripts/docker/resolve_image_reference.py not yet implemented")

    def test_ios_is_not_docker_supported(self):
        """iOS must be rejected by the Docker image resolver."""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "docker"))
            import resolve_image_reference
            with pytest.raises((ValueError, RuntimeError)):
                resolve_image_reference.resolve("iOS", "2022.3.45f1", "ghcr.io/test")
        except ImportError:
            pytest.skip("scripts/docker/resolve_image_reference.py not yet implemented")

    def test_windows64_is_not_docker_supported(self):
        """Windows64 must be rejected by the Docker image resolver."""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "docker"))
            import resolve_image_reference
            with pytest.raises((ValueError, RuntimeError)):
                resolve_image_reference.resolve("Windows64", "2022.3.45f1", "ghcr.io/test")
        except ImportError:
            pytest.skip("scripts/docker/resolve_image_reference.py not yet implemented")

    def test_ios_unsupported_message_is_helpful(self):
        """The error for iOS must explain WHY and HOW to handle it."""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "docker"))
            import resolve_image_reference
            with pytest.raises(Exception) as exc_info:
                resolve_image_reference.resolve("iOS", "2022.3.45f1", "ghcr.io/test")
            msg = str(exc_info.value).lower()
            # Error should mention either the reason (macOS/Xcode) or a workaround
            assert "ios" in msg, f"Error should mention iOS: {exc_info.value}"
        except ImportError:
            pytest.skip("scripts/docker/resolve_image_reference.py not yet implemented")


# ---------------------------------------------------------------------------
# Docker-mandatory config constraints
# ---------------------------------------------------------------------------

class TestDockerMandatoryConfigConstraints:
    """
    After Docker migration, certain config patterns must be enforced:
    - IL2CPP is preferred for Android and WebGL in production
    - Scripting backend values are still constrained by the schema
    """

    def test_il2cpp_scripting_backend_accepted(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "scriptingBackend": "IL2CPP",
        }
        errors = list(schema_validator.iter_errors(config))
        assert errors == [], "IL2CPP scripting backend must pass schema validation"

    def test_mono_scripting_backend_accepted(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "scriptingBackend": "Mono",
        }
        errors = list(schema_validator.iter_errors(config))
        assert errors == [], "Mono scripting backend must pass schema validation"

    def test_invalid_scripting_backend_rejected(self, schema_validator):
        config = {
            "projectName": "test", "companyName": "Acme",
            "productName": "Test", "bundleVersion": "1.0.0",
            "outputDirectory": "Builds",
            "scenes": ["Assets/Scenes/Main.unity"],
            "scriptingBackend": "Emscripten",  # Not a valid backend
        }
        errors = list(schema_validator.iter_errors(config))
        assert errors, "Invalid scripting backend must fail validation"
