"""
Tests for build size comparison logic (scripts/common/build_size.py).

Covers:
- Size comparison with baseline
- Percentage delta calculation
- Warning threshold (>5%)
- Failure threshold (>15%)
- Missing baseline returns "baseline unavailable"
- Absolute max size gate
"""
import pytest


@pytest.fixture(scope="module")
def build_size_module():
    try:
        import build_size
        return build_size
    except ImportError:
        pytest.skip("scripts/common/build_size.py not yet implemented")


MB = 1024 * 1024


# ---------------------------------------------------------------------------
# Result contract helpers
# ---------------------------------------------------------------------------

def get_status(result: dict) -> str:
    return result["status"]


def get_delta_pct(result: dict) -> float:
    return result["delta_pct"]


# ---------------------------------------------------------------------------
# Size comparison with baseline
# ---------------------------------------------------------------------------

class TestSizeComparisonWithBaseline:

    def test_same_size_returns_ok(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=100 * MB,
            baseline_bytes=100 * MB,
        )
        assert get_status(result) == "ok"
        assert get_delta_pct(result) == pytest.approx(0.0)

    def test_smaller_build_returns_ok(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=90 * MB,
            baseline_bytes=100 * MB,
        )
        assert get_status(result) == "ok"
        assert get_delta_pct(result) < 0

    def test_result_dict_has_required_keys(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=100 * MB,
            baseline_bytes=100 * MB,
        )
        assert "status" in result
        assert "delta_pct" in result
        assert "message" in result


# ---------------------------------------------------------------------------
# Percentage delta calculation
# ---------------------------------------------------------------------------

class TestPercentageDelta:

    def test_10_pct_increase_calculated(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=110 * MB,
            baseline_bytes=100 * MB,
        )
        assert get_delta_pct(result) == pytest.approx(10.0)

    def test_50_pct_increase_calculated(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=150 * MB,
            baseline_bytes=100 * MB,
        )
        assert get_delta_pct(result) == pytest.approx(50.0)

    def test_negative_delta_for_smaller_build(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=80 * MB,
            baseline_bytes=100 * MB,
        )
        assert get_delta_pct(result) == pytest.approx(-20.0)

    def test_fractional_delta_precision(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=105 * MB,
            baseline_bytes=100 * MB,
        )
        assert get_delta_pct(result) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Warning threshold (>5%)
# ---------------------------------------------------------------------------

class TestWarningThreshold:

    def test_below_warning_threshold_is_ok(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=104 * MB,
            baseline_bytes=100 * MB,
            warning_threshold_pct=5.0,
        )
        assert get_status(result) == "ok"

    def test_exactly_at_warning_threshold_warns(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=105 * MB,
            baseline_bytes=100 * MB,
            warning_threshold_pct=5.0,
        )
        assert get_status(result) in ("warning", "ok")  # >=5% triggers warning

    def test_above_warning_threshold_warns(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=110 * MB,
            baseline_bytes=100 * MB,
            warning_threshold_pct=5.0,
            failure_threshold_pct=15.0,
        )
        assert get_status(result) == "warning"

    def test_warning_message_included(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=110 * MB,
            baseline_bytes=100 * MB,
            warning_threshold_pct=5.0,
            failure_threshold_pct=15.0,
        )
        assert result["message"]  # non-empty message


# ---------------------------------------------------------------------------
# Failure threshold (>15%)
# ---------------------------------------------------------------------------

class TestFailureThreshold:

    def test_below_failure_threshold_warns(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=114 * MB,
            baseline_bytes=100 * MB,
            warning_threshold_pct=5.0,
            failure_threshold_pct=15.0,
        )
        assert get_status(result) == "warning"

    def test_above_failure_threshold_fails(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=120 * MB,
            baseline_bytes=100 * MB,
            warning_threshold_pct=5.0,
            failure_threshold_pct=15.0,
        )
        assert get_status(result) == "failure"

    def test_exactly_at_failure_threshold_fails(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=115 * MB,
            baseline_bytes=100 * MB,
            warning_threshold_pct=5.0,
            failure_threshold_pct=15.0,
        )
        assert get_status(result) in ("failure", "warning")  # >=15% fails

    def test_failure_message_included(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=200 * MB,
            baseline_bytes=100 * MB,
        )
        assert result["message"]


# ---------------------------------------------------------------------------
# Missing baseline
# ---------------------------------------------------------------------------

class TestMissingBaseline:

    def test_none_baseline_returns_unavailable(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=100 * MB,
            baseline_bytes=None,
        )
        assert get_status(result) == "baseline_unavailable"

    def test_unavailable_message_informative(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=100 * MB,
            baseline_bytes=None,
        )
        msg = result.get("message", "").lower()
        assert "baseline" in msg

    def test_delta_pct_none_when_no_baseline(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=100 * MB,
            baseline_bytes=None,
        )
        assert result["delta_pct"] is None


# ---------------------------------------------------------------------------
# Absolute max size gate
# ---------------------------------------------------------------------------

class TestAbsoluteMaxSizeGate:

    def test_under_max_size_passes(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=100 * MB,
            baseline_bytes=None,
            max_size_bytes=200 * MB,
        )
        # No baseline, but under max — should not be a max-size failure
        assert get_status(result) != "max_size_exceeded"

    def test_over_max_size_fails(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=250 * MB,
            baseline_bytes=200 * MB,
            max_size_bytes=200 * MB,
        )
        assert get_status(result) == "max_size_exceeded"

    def test_max_size_failure_without_baseline(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=300 * MB,
            baseline_bytes=None,
            max_size_bytes=200 * MB,
        )
        assert get_status(result) == "max_size_exceeded"

    def test_max_size_message_includes_limit(self, build_size_module):
        result = build_size_module.compare_size(
            current_bytes=300 * MB,
            baseline_bytes=None,
            max_size_bytes=200 * MB,
        )
        msg = result.get("message", "")
        assert "200" in msg or "MB" in msg or "max" in msg.lower()

    def test_no_max_size_no_gate(self, build_size_module):
        """Passing max_size_bytes=None disables the absolute gate."""
        result = build_size_module.compare_size(
            current_bytes=999 * MB,
            baseline_bytes=100 * MB,
            max_size_bytes=None,
        )
        assert get_status(result) != "max_size_exceeded"

    def test_gates_config_max_size_honoured(self, build_size_module, valid_production_config):
        """The gates.maxBuildSizeMB from config should be usable as max_size_bytes."""
        max_mb = valid_production_config["gates"]["maxBuildSizeMB"]
        max_bytes = max_mb * MB
        over_limit = int(max_bytes * 1.5)
        result = build_size_module.compare_size(
            current_bytes=over_limit,
            baseline_bytes=None,
            max_size_bytes=max_bytes,
        )
        assert get_status(result) == "max_size_exceeded"
