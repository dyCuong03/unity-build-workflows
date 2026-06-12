"""
Build metadata generation library for Unity build pipeline.

Generates structured build metadata JSON with project info,
git context, timing, artifacts, and cache status.
"""
from datetime import datetime, timezone


def generate_metadata(
    project=None,
    project_name=None,
    git_commit=None,
    git_sha=None,
    git_branch=None,
    git_tag=None,
    unity_version=None,
    platform=None,
    build_target=None,
    environment=None,
    version=None,
    build_id=None,
    build_number=None,
    release_mode=False,
    build_started_at=None,
    build_finished_at=None,
    start_time=None,
    end_time=None,
    artifact=None,
    artifact_size_bytes=0,
    warnings=0,
    errors=0,
    cache_mode=None,
    cache_hit=False,
    cache_status=None,
    success=True,
    **extra
):
    """Generate a complete build metadata dictionary.

    Accepts both camelCase-style and snake_case-style parameter names
    for flexibility across different callers.

    Returns:
        Dictionary with camelCase metadata fields.
    """
    # Normalize aliased params
    _project = project or project_name
    _commit = git_commit or git_sha
    _platform = platform or build_target
    _start = build_started_at or start_time
    _end = build_finished_at or end_time
    _cache_status = cache_status or cache_mode or ("hit" if cache_hit else None)

    duration = None
    if _start and _end:
        duration = calculate_duration(_start, _end)

    artifact_size_mb = round(artifact_size_bytes / (1024 * 1024), 2) if artifact_size_bytes else 0.0

    metadata = {
        "project": _project,
        "buildId": build_id,
        "gitCommit": _commit,
        "gitBranch": git_branch,
        "gitTag": git_tag,
        "unityVersion": unity_version,
        "buildTarget": _platform,
        "environment": environment,
        "version": version,
        "buildNumber": build_number,
        "releaseMode": release_mode,
        "startTime": _start,
        "endTime": _end,
        "durationSeconds": duration,
        "artifact": artifact,
        "artifactSizeBytes": artifact_size_bytes,
        "artifactSizeMB": artifact_size_mb,
        "warnings": warnings,
        "errors": errors,
        "cacheStatus": _cache_status,
        "cacheHit": cache_hit,
        "success": success,
    }

    metadata.update(extra)
    return metadata


def calculate_duration(start_iso, end_iso):
    """Calculate duration in seconds between two ISO-8601 timestamps.

    Args:
        start_iso: Start time as ISO-8601 string (e.g. "2026-06-12T08:00:00Z").
        end_iso: End time as ISO-8601 string.

    Returns:
        Duration in seconds (float).

    Raises:
        ValueError: If end is before start.
    """
    start = _parse_iso(start_iso)
    end = _parse_iso(end_iso)

    delta = (end - start).total_seconds()
    if delta < 0:
        raise ValueError(
            f"End time ({end_iso}) is before start time ({start_iso})"
        )
    return delta


def _parse_iso(timestamp_str):
    """Parse ISO-8601 timestamp string to datetime."""
    ts = timestamp_str.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)
