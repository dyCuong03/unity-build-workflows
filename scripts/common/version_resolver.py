"""
Version resolution library for Unity build pipeline.

Provides functions for resolving, validating, and formatting version strings
from build configs, git tags, and environment context.
"""
import re


_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def resolve_version(config_version=None, git_tag=None):
    """Resolve the final version string.

    If both config_version and git_tag are provided, they must match.
    git_tag takes precedence when both are present and match.

    Args:
        config_version: Version from BuildConfig (e.g. "1.4.0")
        git_tag: Git tag string (e.g. "v1.4.0" or "1.4.0")

    Returns:
        Resolved version string (e.g. "1.4.0")

    Raises:
        ValueError: If no version source provided or tag/config mismatch.
    """
    if config_version is None and git_tag is None:
        raise ValueError("No version source provided: need config_version or git_tag")

    tag_version = parse_git_tag(git_tag) if git_tag else None

    if tag_version and config_version:
        if tag_version != config_version:
            raise ValueError(
                f"Version mismatch: git tag '{git_tag}' resolves to '{tag_version}' "
                f"but config has '{config_version}'"
            )
        return tag_version

    if tag_version:
        return tag_version

    return config_version


def parse_git_tag(tag):
    """Parse a git tag into a clean version string.

    Strips 'v' prefix if present.

    Args:
        tag: Git tag string (e.g. "v1.4.0" or "1.4.0")

    Returns:
        Clean version string (e.g. "1.4.0")
    """
    if tag is None:
        return None
    tag = tag.strip()
    if tag.startswith("v") or tag.startswith("V"):
        return tag[1:]
    return tag


def validate_version_format(version):
    """Validate that a version string matches semantic versioning (X.Y.Z).

    Args:
        version: Version string to validate.

    Returns:
        The version string if valid.

    Raises:
        ValueError: If version format is invalid.
    """
    if not version or not _SEMVER_PATTERN.match(version):
        raise ValueError(f"Invalid version format: '{version}'. Expected X.Y.Z (e.g. 1.4.0)")
    return version


def build_number_from_run_number(run_number):
    """Convert a CI run number to an integer build number.

    Args:
        run_number: String or int run number.

    Returns:
        Integer build number.

    Raises:
        ValueError: If run_number is not numeric.
    """
    try:
        return int(run_number)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid run number: '{run_number}'. Must be numeric.")


def apply_environment_suffix(version, environment):
    """Append environment suffix to version string.

    Production and None environments get no suffix.
    Prevents double-appending if suffix already present.

    Args:
        version: Base version string (e.g. "1.4.0")
        environment: Environment name (e.g. "staging", "development", "production", None)

    Returns:
        Version with suffix (e.g. "1.4.0-staging") or unchanged for production/None.
    """
    if not environment or environment.lower() == "production":
        return version

    suffix = f"-{environment.lower()}"
    if version.endswith(suffix):
        return version

    return f"{version}{suffix}"
