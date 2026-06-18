"""
Tests for build metadata generation (scripts/common/build_metadata.py).

Covers:
- Metadata JSON structure
- Required fields present
- Duration calculation
- Artifact size recording
- Cache status recording
"""
from datetime import datetime, timezone

import pytest


@pytest.fixture(scope="module")
def build_metadata_module():
    try:
        import build_metadata
        return build_metadata
    except ImportError:
        pytest.skip("scripts/common/build_metadata.py not yet implemented")


@pytest.fixture
def sample_metadata_kwargs():
    return {
        "build_id": "run-1234",
        "version": "1.4.0",
        "build_number": 1234,
        "build_target": "Android",
        "environment": "production",
        "start_time": "2026-06-12T10:00:00Z",
        "end_time": "2026-06-12T10:30:00Z",
        "artifact_size_bytes": 104857600,
        "cache_status": "hit",
        "success": True,
        "unity_version": "2022.3.45f1",
        "project_name": "example-project",
        "git_sha": "abc1234def5678",
        "git_branch": "main",
    }


# ---------------------------------------------------------------------------
# Metadata structure
# ---------------------------------------------------------------------------

class TestMetadataStructure:

    REQUIRED_FIELDS = {
        "buildId", "version", "buildTarget", "environment",
        "startTime", "endTime", "durationSeconds",
        "artifactSizeBytes", "cacheStatus", "success",
    }

    def test_generate_metadata_returns_dict(
        self, build_metadata_module, sample_metadata_kwargs
    ):
        result = build_metadata_module.generate_metadata(**sample_metadata_kwargs)
        assert isinstance(result, dict)

    def test_all_required_fields_present(
        self, build_metadata_module, sample_metadata_kwargs
    ):
        result = build_metadata_module.generate_metadata(**sample_metadata_kwargs)
        missing = self.REQUIRED_FIELDS - set(result.keys())
        assert not missing, f"Missing required fields: {missing}"

    def test_metadata_matches_sample_fixture(
        self, build_metadata_module, build_metadata_sample, sample_metadata_kwargs
    ):
        result = build_metadata_module.generate_metadata(**sample_metadata_kwargs)
        assert result["buildId"] == build_metadata_sample["buildId"]
        assert result["version"] == build_metadata_sample["version"]
        assert result["buildTarget"] == build_metadata_sample["buildTarget"]
        assert result["environment"] == build_metadata_sample["environment"]

    def test_build_id_preserved(self, build_metadata_module, sample_metadata_kwargs):
        result = build_metadata_module.generate_metadata(**sample_metadata_kwargs)
        assert result["buildId"] == "run-1234"

    def test_success_flag_false(self, build_metadata_module, sample_metadata_kwargs):
        kwargs = {**sample_metadata_kwargs, "success": False}
        result = build_metadata_module.generate_metadata(**kwargs)
        assert result["success"] is False

    def test_success_flag_true(self, build_metadata_module, sample_metadata_kwargs):
        result = build_metadata_module.generate_metadata(**sample_metadata_kwargs)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Duration calculation
# ---------------------------------------------------------------------------

class TestDurationCalculation:

    def test_duration_calculated_correctly(self, build_metadata_module):
        duration = build_metadata_module.calculate_duration(
            "2026-06-12T10:00:00Z",
            "2026-06-12T10:30:00Z",
        )
        assert duration == 1800

    def test_duration_in_metadata_matches(
        self, build_metadata_module, sample_metadata_kwargs
    ):
        result = build_metadata_module.generate_metadata(**sample_metadata_kwargs)
        # 30 minutes = 1800 seconds
        assert result["durationSeconds"] == 1800

    def test_duration_short_build(self, build_metadata_module):
        duration = build_metadata_module.calculate_duration(
            "2026-06-12T10:00:00Z",
            "2026-06-12T10:00:45Z",
        )
        assert duration == 45

    def test_duration_multi_hour_build(self, build_metadata_module):
        duration = build_metadata_module.calculate_duration(
            "2026-06-12T08:00:00Z",
            "2026-06-12T10:15:00Z",
        )
        assert duration == 8100  # 2h 15m

    def test_duration_is_non_negative(self, build_metadata_module):
        duration = build_metadata_module.calculate_duration(
            "2026-06-12T10:00:00Z",
            "2026-06-12T10:00:00Z",
        )
        assert duration == 0

    def test_duration_end_before_start_raises(self, build_metadata_module):
        with pytest.raises((ValueError, AssertionError)):
            build_metadata_module.calculate_duration(
                "2026-06-12T10:30:00Z",
                "2026-06-12T10:00:00Z",
            )


# ---------------------------------------------------------------------------
# Artifact size recording
# ---------------------------------------------------------------------------

class TestArtifactSizeRecording:

    def test_artifact_size_bytes_recorded(
        self, build_metadata_module, sample_metadata_kwargs
    ):
        result = build_metadata_module.generate_metadata(**sample_metadata_kwargs)
        assert result["artifactSizeBytes"] == 104857600

    def test_artifact_size_mb_derived(
        self, build_metadata_module, sample_metadata_kwargs
    ):
        result = build_metadata_module.generate_metadata(**sample_metadata_kwargs)
        if "artifactSizeMB" in result:
            expected_mb = 104857600 / (1024 * 1024)
            assert abs(result["artifactSizeMB"] - expected_mb) < 0.01

    def test_zero_artifact_size_allowed(
        self, build_metadata_module, sample_metadata_kwargs
    ):
        kwargs = {**sample_metadata_kwargs, "artifact_size_bytes": 0}
        result = build_metadata_module.generate_metadata(**kwargs)
        assert result["artifactSizeBytes"] == 0

    def test_large_artifact_size(self, build_metadata_module, sample_metadata_kwargs):
        one_gb = 1024 * 1024 * 1024
        kwargs = {**sample_metadata_kwargs, "artifact_size_bytes": one_gb}
        result = build_metadata_module.generate_metadata(**kwargs)
        assert result["artifactSizeBytes"] == one_gb


# ---------------------------------------------------------------------------
# Cache status recording
# ---------------------------------------------------------------------------

class TestCacheStatusRecording:

    @pytest.mark.parametrize("status", ["hit", "miss", "disabled"])
    def test_cache_status_recorded(
        self, build_metadata_module, sample_metadata_kwargs, status
    ):
        kwargs = {**sample_metadata_kwargs, "cache_status": status}
        result = build_metadata_module.generate_metadata(**kwargs)
        assert result["cacheStatus"] == status

    def test_cache_hit_in_sample(
        self, build_metadata_module, build_metadata_sample
    ):
        assert build_metadata_sample["cacheStatus"] == "hit"
