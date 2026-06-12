"""
Tests for version resolution logic (scripts/common/version_resolver.py).

Covers:
- Version from config
- Version from git tag
- Tag/config mismatch detection
- Build number from run number
- Environment suffix
- Invalid version format rejection
"""
import pytest


@pytest.fixture(scope="module")
def version_resolver():
    """Import version_resolver, skip if not yet implemented."""
    try:
        import version_resolver
        return version_resolver
    except ImportError:
        pytest.skip("scripts/common/version_resolver.py not yet implemented")


# ---------------------------------------------------------------------------
# Version from config
# ---------------------------------------------------------------------------

class TestVersionFromConfig:

    def test_version_from_config_returned_as_is(self, version_resolver):
        version = version_resolver.resolve_version(config_version="1.4.0")
        assert version == "1.4.0"

    def test_version_with_different_values(self, version_resolver):
        assert version_resolver.resolve_version(config_version="2.0.0") == "2.0.0"
        assert version_resolver.resolve_version(config_version="0.1.99") == "0.1.99"

    def test_no_version_raises(self, version_resolver):
        with pytest.raises((ValueError, TypeError)):
            version_resolver.resolve_version()


# ---------------------------------------------------------------------------
# Version from git tag
# ---------------------------------------------------------------------------

class TestVersionFromGitTag:

    def test_tag_v_prefix_stripped(self, version_resolver):
        version = version_resolver.parse_git_tag("v1.4.0")
        assert version == "1.4.0"

    def test_tag_without_v_prefix(self, version_resolver):
        version = version_resolver.parse_git_tag("1.4.0")
        assert version == "1.4.0"

    def test_tag_preferred_over_config_when_both_match(self, version_resolver):
        version = version_resolver.resolve_version(
            config_version="1.4.0", git_tag="v1.4.0"
        )
        assert version == "1.4.0"

    def test_various_tag_formats(self, version_resolver):
        assert version_resolver.parse_git_tag("v0.0.1") == "0.0.1"
        assert version_resolver.parse_git_tag("v10.20.300") == "10.20.300"


# ---------------------------------------------------------------------------
# Tag/config mismatch detection
# ---------------------------------------------------------------------------

class TestVersionMismatchDetection:

    def test_tag_config_mismatch_raises(self, version_resolver):
        with pytest.raises(ValueError, match=r"[Mm]ismatch|mismatch|differ"):
            version_resolver.resolve_version(
                config_version="1.4.0", git_tag="v1.5.0"
            )

    def test_matching_tag_and_config_does_not_raise(self, version_resolver):
        # Should not raise
        version_resolver.resolve_version(
            config_version="2.3.1", git_tag="v2.3.1"
        )

    def test_tag_without_v_prefix_mismatch_detected(self, version_resolver):
        with pytest.raises(ValueError):
            version_resolver.resolve_version(
                config_version="1.0.0", git_tag="2.0.0"
            )


# ---------------------------------------------------------------------------
# Build number from run number
# ---------------------------------------------------------------------------

class TestBuildNumber:

    def test_build_number_from_run_number(self, version_resolver):
        assert version_resolver.build_number_from_run_number("42") == 42
        assert version_resolver.build_number_from_run_number(100) == 100

    def test_build_number_is_integer(self, version_resolver):
        result = version_resolver.build_number_from_run_number("999")
        assert isinstance(result, int)

    def test_build_number_zero_run(self, version_resolver):
        # Run numbers start at 1 in GitHub Actions, but we should not crash on 0
        result = version_resolver.build_number_from_run_number(0)
        assert result == 0

    def test_non_numeric_run_number_raises(self, version_resolver):
        with pytest.raises((ValueError, TypeError)):
            version_resolver.build_number_from_run_number("not-a-number")


# ---------------------------------------------------------------------------
# Environment suffix
# ---------------------------------------------------------------------------

class TestEnvironmentSuffix:

    def test_staging_suffix_appended(self, version_resolver):
        result = version_resolver.apply_environment_suffix("1.4.0", "staging")
        assert result == "1.4.0-staging"

    def test_development_suffix_appended(self, version_resolver):
        result = version_resolver.apply_environment_suffix("1.4.0", "development")
        assert result == "1.4.0-development"

    def test_production_no_suffix(self, version_resolver):
        result = version_resolver.apply_environment_suffix("1.4.0", "production")
        assert result == "1.4.0"

    def test_no_environment_no_suffix(self, version_resolver):
        result = version_resolver.apply_environment_suffix("1.4.0", None)
        assert result == "1.4.0"

    def test_suffix_does_not_double_append(self, version_resolver):
        # Calling twice with the same env should not stack suffixes
        once = version_resolver.apply_environment_suffix("1.4.0", "staging")
        twice = version_resolver.apply_environment_suffix(once, "staging")
        assert twice == "1.4.0-staging"


# ---------------------------------------------------------------------------
# Invalid version format rejection
# ---------------------------------------------------------------------------

class TestVersionFormatValidation:

    @pytest.mark.parametrize("bad_version", [
        "1.0",        # missing patch
        "1",          # only major
        "1.0.0.0",    # four segments
        "v1.0.0",     # has v-prefix (not a bare version)
        "1.0.a",      # non-numeric patch
        "",           # empty string
        "latest",     # symbolic
    ])
    def test_invalid_version_format_rejected(self, version_resolver, bad_version):
        with pytest.raises((ValueError, AssertionError)):
            version_resolver.validate_version_format(bad_version)

    @pytest.mark.parametrize("good_version", [
        "1.0.0",
        "2.10.300",
        "0.0.1",
        "99.99.99",
    ])
    def test_valid_version_format_accepted(self, version_resolver, good_version):
        # Should return True or the version string without raising
        result = version_resolver.validate_version_format(good_version)
        assert result is not False
