"""
Build size comparison library for Unity build pipeline.

Compares current build artifact size against a baseline and
applies configurable warning/failure thresholds.
"""


def compare_size(
    current_bytes,
    baseline_bytes=None,
    warning_threshold_pct=5.0,
    failure_threshold_pct=15.0,
    max_size_bytes=None,
):
    """Compare current build size against baseline with threshold gates.

    Args:
        current_bytes: Current artifact size in bytes.
        baseline_bytes: Previous artifact size in bytes (None if no baseline).
        warning_threshold_pct: Percentage increase that triggers warning.
        failure_threshold_pct: Percentage increase that triggers failure.
        max_size_bytes: Absolute maximum size in bytes (None to skip gate).

    Returns:
        dict with keys:
            - status: "ok", "warning", "failure", "max_size_exceeded", or "baseline_unavailable"
            - delta_bytes: Absolute size change (None if no baseline)
            - delta_pct: Percentage change (None if no baseline)
            - current_bytes: Current size
            - baseline_bytes: Baseline size (None if unavailable)
            - message: Human-readable description
    """
    result = {
        "current_bytes": current_bytes,
        "baseline_bytes": baseline_bytes,
        "delta_bytes": None,
        "delta_pct": None,
        "status": "ok",
        "message": "",
    }

    # Check absolute max size gate first (applies regardless of baseline)
    if max_size_bytes is not None and current_bytes > max_size_bytes:
        result["status"] = "max_size_exceeded"
        max_mb = round(max_size_bytes / (1024 * 1024), 2)
        current_mb = round(current_bytes / (1024 * 1024), 2)
        result["message"] = (
            f"Build size {current_mb} MB exceeds maximum allowed {max_mb} MB"
        )
        return result

    # No baseline available
    if baseline_bytes is None:
        result["status"] = "baseline_unavailable"
        result["message"] = "baseline unavailable"
        return result

    # Calculate deltas
    delta_bytes = current_bytes - baseline_bytes
    if baseline_bytes > 0:
        delta_pct = round((delta_bytes / baseline_bytes) * 100, 2)
    else:
        delta_pct = 0.0 if delta_bytes == 0 else 100.0

    result["delta_bytes"] = delta_bytes
    result["delta_pct"] = delta_pct

    # Apply thresholds (only on increases)
    if delta_pct >= failure_threshold_pct:
        result["status"] = "failure"
        result["message"] = (
            f"Build size increased by {delta_pct}% ({delta_bytes:+d} bytes), "
            f"exceeding failure threshold of {failure_threshold_pct}%"
        )
    elif delta_pct >= warning_threshold_pct:
        result["status"] = "warning"
        result["message"] = (
            f"Build size increased by {delta_pct}% ({delta_bytes:+d} bytes), "
            f"exceeding warning threshold of {warning_threshold_pct}%"
        )
    else:
        direction = "increased" if delta_bytes > 0 else "decreased" if delta_bytes < 0 else "unchanged"
        result["status"] = "ok"
        result["message"] = f"Build size {direction} by {abs(delta_pct)}% ({abs(delta_bytes)} bytes)"

    return result
