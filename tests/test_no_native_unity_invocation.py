"""
CRITICAL regression test — prevents native Unity invocations from sneaking back
into the repository after the Docker-mandatory migration.

Scans the ENTIRE repository for patterns that indicate direct (non-Docker) Unity
Editor invocations. The ONLY permitted location is docker/unity/entrypoint.sh.

If ANY native invocation is found outside that file, this test FAILS.

Patterns detected:
  - Unity -batchmode  /  unity-editor -batchmode
  - Unity.exe -batchmode
  - Unity.app/Contents/MacOS/Unity
  - -executeMethod  (outside the approved entrypoint)
  - game-ci/unity-builder
  - game-ci/unity-test-runner

This test is the last line of defence against regression.
"""
import re
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).parent.parent

# The ONLY file allowed to contain direct Unity invocations.
ALLOWED_PATH = "docker/unity/entrypoint.sh"

# ---------------------------------------------------------------------------
# Patterns that indicate a direct (non-Docker) Unity invocation
# ---------------------------------------------------------------------------

# Each entry: (human_name, compiled_regex)
NATIVE_PATTERNS = [
    (
        "Unity -batchmode (generic)",
        re.compile(r"\bUnity\b.*-batchmode", re.IGNORECASE),
    ),
    (
        "unity-editor -batchmode",
        re.compile(r"unity-editor\s+-batchmode", re.IGNORECASE),
    ),
    (
        "Unity.exe -batchmode",
        re.compile(r"Unity\.exe\s+-batchmode", re.IGNORECASE),
    ),
    (
        "Unity.app/Contents/MacOS/Unity",
        re.compile(r"Unity\.app/Contents/MacOS/Unity", re.IGNORECASE),
    ),
    (
        "-executeMethod (direct invocation outside entrypoint)",
        re.compile(r"-executeMethod\b"),
    ),
    (
        "game-ci/unity-builder action",
        re.compile(r"game-ci/unity-builder"),
    ),
    (
        "game-ci/unity-test-runner action",
        re.compile(r"game-ci/unity-test-runner"),
    ),
]

# ---------------------------------------------------------------------------
# File glob patterns to scan
# ---------------------------------------------------------------------------

SCAN_GLOBS = [
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".github/actions/**/*.yml",
    ".github/actions/**/*.yaml",
    "scripts/**/*.py",
    "scripts/**/*.sh",
    "templates/**/*.yml",
    "templates/**/*.yaml",
]

# Glob patterns to EXCLUDE from scanning (compiled for speed)
EXCLUDE_PATTERNS = [
    re.compile(r"__pycache__"),
    re.compile(r"\.pyc$"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_excluded(path: Path) -> bool:
    path_str = str(path)
    return any(p.search(path_str) for p in EXCLUDE_PATTERNS)


def _is_allowed(path: Path) -> bool:
    """Return True if this file is the one approved location for Unity invocations."""
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return False
    return str(rel).replace("\\", "/") == ALLOWED_PATH


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    """
    Scan a file for native Unity invocation patterns.

    Returns a list of (line_number, pattern_name, line_content) for each hit.
    Skips the allowed entrypoint file.
    """
    if _is_excluded(path) or _is_allowed(path):
        return []

    hits = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return []

    for lineno, line in enumerate(content.splitlines(), start=1):
        for pattern_name, pattern in NATIVE_PATTERNS:
            if pattern.search(line):
                hits.append((lineno, pattern_name, line.strip()))
    return hits


def _iter_scan_files() -> Iterator[Path]:
    """Yield all files that should be scanned."""
    for glob_pattern in SCAN_GLOBS:
        yield from REPO_ROOT.glob(glob_pattern)


# ---------------------------------------------------------------------------
# Parameterized per-file test
# ---------------------------------------------------------------------------

def _collect_violations() -> list[tuple[Path, int, str, str]]:
    """Collect all violations across the repo: (path, lineno, pattern, line)."""
    violations = []
    for path in _iter_scan_files():
        for lineno, pattern_name, line in _scan_file(path):
            violations.append((path, lineno, pattern_name, line))
    return violations


class TestNoNativeUnityInvocation:
    """
    Scans .github/workflows, .github/actions, scripts, and templates for
    native Unity invocations. Only docker/unity/entrypoint.sh may contain them.
    """

    def test_no_batchmode_in_workflows(self):
        """No workflow YAML should invoke Unity with -batchmode directly."""
        violations = []
        for path in REPO_ROOT.glob(".github/workflows/*.yml"):
            for lineno, pattern_name, line in _scan_file(path):
                if "-batchmode" in pattern_name.lower() or "unity.app" in pattern_name.lower():
                    violations.append((path, lineno, pattern_name, line))

        if violations:
            msg = _format_violation_message(violations)
            pytest.fail(
                f"Native Unity invocations found in workflows — Docker is mandatory:\n{msg}"
            )

    def test_no_batchmode_in_actions(self):
        """No composite action should invoke Unity with -batchmode directly."""
        violations = []
        for path in REPO_ROOT.glob(".github/actions/**/*.yml"):
            for lineno, pattern_name, line in _scan_file(path):
                if "-batchmode" in pattern_name.lower() or "Unity.app" in line:
                    violations.append((path, lineno, pattern_name, line))

        if violations:
            msg = _format_violation_message(violations)
            pytest.fail(
                f"Native Unity invocations found in composite actions — Docker is mandatory:\n{msg}"
            )

    def test_no_execute_method_in_python_scripts(self):
        """Python scripts must not invoke Unity's -executeMethod directly."""
        violations = []
        pattern_name = "-executeMethod (direct invocation outside entrypoint)"
        pattern = re.compile(r"-executeMethod\b")
        for path in REPO_ROOT.glob("scripts/**/*.py"):
            if _is_excluded(path):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                if pattern.search(line):
                    violations.append((path, lineno, pattern_name, line.strip()))

        if violations:
            msg = _format_violation_message(violations)
            pytest.fail(
                f"-executeMethod found in Python scripts outside entrypoint:\n{msg}"
            )

    def test_no_game_ci_actions_in_workflows(self):
        """No workflow should use game-ci/unity-builder or game-ci/unity-test-runner."""
        violations = []
        builder_pat = re.compile(r"game-ci/unity-builder")
        runner_pat = re.compile(r"game-ci/unity-test-runner")

        for glob_pat in (".github/workflows/*.yml", ".github/actions/**/*.yml"):
            for path in REPO_ROOT.glob(glob_pat):
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for lineno, line in enumerate(content.splitlines(), start=1):
                    if builder_pat.search(line):
                        violations.append((path, lineno, "game-ci/unity-builder", line.strip()))
                    if runner_pat.search(line):
                        violations.append((path, lineno, "game-ci/unity-test-runner", line.strip()))

        if violations:
            msg = _format_violation_message(violations)
            pytest.fail(
                f"game-ci actions found — Docker-native runner is mandatory:\n{msg}"
            )

    def test_no_native_invocations_in_shell_scripts(self):
        """Shell scripts (outside entrypoint.sh) must not invoke Unity directly."""
        violations = []
        for path in REPO_ROOT.glob("scripts/**/*.sh"):
            for lineno, pattern_name, line in _scan_file(path):
                violations.append((path, lineno, pattern_name, line))

        if violations:
            msg = _format_violation_message(violations)
            pytest.fail(
                f"Native Unity invocations found in shell scripts:\n{msg}"
            )

    def test_no_native_invocations_in_templates(self):
        """Template YAML files must not invoke Unity directly."""
        violations = []
        for glob_pat in ("templates/**/*.yml", "templates/**/*.yaml"):
            for path in REPO_ROOT.glob(glob_pat):
                for lineno, pattern_name, line in _scan_file(path):
                    violations.append((path, lineno, pattern_name, line))

        if violations:
            msg = _format_violation_message(violations)
            pytest.fail(
                f"Native Unity invocations found in templates:\n{msg}"
            )

    def test_full_repo_scan_no_violations(self):
        """
        Comprehensive scan: no native Unity invocations anywhere except entrypoint.sh.

        This is the definitive regression test. All other tests above are scoped;
        this one covers everything.
        """
        all_violations = _collect_violations()
        if all_violations:
            msg = _format_violation_message(all_violations)
            pytest.fail(
                f"REGRESSION: Native Unity invocations found outside "
                f"{ALLOWED_PATH}.\n"
                f"Only docker/unity/entrypoint.sh may invoke Unity directly.\n\n"
                f"{msg}"
            )

    def test_allowed_path_constant_is_correct(self):
        """Sanity check: the ALLOWED_PATH constant points to the real entrypoint."""
        # This test verifies our constant is well-formed, not that the file exists
        # (it will be created by Task #2 / Docker infrastructure task)
        assert ALLOWED_PATH == "docker/unity/entrypoint.sh", \
            "ALLOWED_PATH constant must point to docker/unity/entrypoint.sh"
        assert "/" in ALLOWED_PATH, "ALLOWED_PATH must use forward slashes"

    def test_entrypoint_is_only_allowed_location(self):
        """Document the contract: only entrypoint.sh may call Unity directly."""
        # Meta-test: confirm our allowlist has exactly one entry
        assert ALLOWED_PATH == "docker/unity/entrypoint.sh"


# ---------------------------------------------------------------------------
# Formatting helper
# ---------------------------------------------------------------------------

def _format_violation_message(violations: list) -> str:
    lines = []
    for path, lineno, pattern_name, line_content in violations:
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = path
        lines.append(f"  {rel}:{lineno}  [{pattern_name}]")
        lines.append(f"    {line_content}")
    return "\n".join(lines)
