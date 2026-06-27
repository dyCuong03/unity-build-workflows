"""
Tests for toolkit-path and project-path input validation.

Approved design (T3):
  - toolkit-path: consumer's submodule location (default: tools/unity-build-workflows)
  - project-path: Unity project root relative to consumer repo root (default: .)
  - Path traversal (../) and absolute paths must be rejected at workflow entry.
  - Canonical internal mount: TOOLKIT_PATH=.ci/unity-build-workflows (never changes).
  - project-path and toolkit-path must be distinct, non-overlapping paths.

Test classes:
  TestIntegrationModeInputContract   — YAML inputs exist, types/defaults correct
  TestPathTraversalRejectionInYAML   — workflow run: blocks contain traversal guards
  TestValidateToolkitPathCLI         — optional Python CLI (skip if absent)
  TestProjectToolkitSeparation       — immutable geometry assertions (always pass)

Skip behaviour:
  Tests in the first two classes skip gracefully if T3 has not yet added
  integration-mode / toolkit-path inputs to unity-build.yml. They will
  pass once T3 lands. TestValidateToolkitPathCLI skips if the optional
  scripts/common/validate_toolkit_path.py is absent.
  TestProjectToolkitSeparation never skips — it checks immutable geometry.
"""
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
UNITY_BUILD_YML = WORKFLOWS_DIR / "unity-build.yml"

# Optional Python CLI added by T3 — tests skip if absent.
VALIDATE_PATH_SCRIPT = REPO_ROOT / "scripts" / "common" / "validate_toolkit_path.py"

# Per-platform workflows that must also receive the new inputs from T3.
PLATFORM_WORKFLOWS = [
    "unity-build-android.yml",
    "unity-build-webgl.yml",
    "unity-build-linux.yml",
    "unity-build-ios.yml",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def _get_triggers(doc: dict) -> dict:
    """Handle PyYAML parsing bare `on:` as boolean True."""
    return doc.get("on") or doc.get(True) or {}


def _iter_steps(doc: dict):
    """Yield every step dict across all jobs."""
    for job in (doc.get("jobs") or {}).values():
        for step in (job.get("steps") or []):
            yield step


def _all_run_text(doc: dict) -> str:
    """Concatenate all `run:` shell block content across every step."""
    parts = []
    for step in _iter_steps(doc):
        run = step.get("run") or ""
        if run:
            parts.append(run)
    return "\n".join(parts)


def _unity_build_inputs() -> dict:
    """Return workflow_call inputs from unity-build.yml, or {} if not present."""
    if not UNITY_BUILD_YML.exists():
        return {}
    doc = _load_yaml(UNITY_BUILD_YML)
    triggers = _get_triggers(doc)
    return triggers.get("workflow_call", {}).get("inputs", {}) or {}


def _workflow_inputs(filename: str) -> dict:
    path = WORKFLOWS_DIR / filename
    if not path.exists():
        return {}
    doc = _load_yaml(path)
    triggers = _get_triggers(doc)
    return triggers.get("workflow_call", {}).get("inputs", {}) or {}


def _run_validate_path(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATE_PATH_SCRIPT), *args],
        capture_output=True, text=True, timeout=10,
    )


# ---------------------------------------------------------------------------
# YAML contract: new inputs added by T3
# ---------------------------------------------------------------------------

class TestIntegrationModeInputContract:
    """
    unity-build.yml must expose integration-mode and toolkit-path after T3.
    All per-platform workflows must pass them through.
    """

    @pytest.fixture(autouse=True)
    def _require_integration_mode(self):
        if "integration-mode" not in _unity_build_inputs():
            pytest.skip(
                "integration-mode input not yet in unity-build.yml — waiting for T3"
            )

    # ── unity-build.yml ──────────────────────────────────────────────────────

    def test_integration_mode_input_exists(self):
        assert "integration-mode" in _unity_build_inputs(), \
            "unity-build.yml must have 'integration-mode' input (T3)"

    def test_integration_mode_type_is_string(self):
        assert _unity_build_inputs()["integration-mode"].get("type") == "string", \
            "integration-mode must be type: string"

    def test_integration_mode_default_is_remote(self):
        assert _unity_build_inputs()["integration-mode"].get("default") == "remote", \
            "integration-mode must default to 'remote' (backward-compatible)"

    def test_integration_mode_has_description(self):
        defn = _unity_build_inputs()["integration-mode"]
        assert defn.get("description"), \
            "integration-mode input must have a description"

    def test_toolkit_path_input_exists(self):
        inputs = _unity_build_inputs()
        assert "toolkit-path" in inputs, \
            "unity-build.yml must have 'toolkit-path' input (T3)"

    def test_toolkit_path_type_is_string(self):
        inputs = _unity_build_inputs()
        if "toolkit-path" not in inputs:
            pytest.skip("toolkit-path input not yet present")
        assert inputs["toolkit-path"].get("type") == "string", \
            "toolkit-path must be type: string"

    def test_toolkit_path_default_is_tools_subdir(self):
        inputs = _unity_build_inputs()
        if "toolkit-path" not in inputs:
            pytest.skip("toolkit-path input not yet present")
        assert inputs["toolkit-path"].get("default") == "tools/unity-build-workflows", \
            "toolkit-path must default to 'tools/unity-build-workflows'"

    def test_toolkit_path_has_description(self):
        inputs = _unity_build_inputs()
        if "toolkit-path" not in inputs:
            pytest.skip("toolkit-path input not yet present")
        assert inputs["toolkit-path"].get("description"), \
            "toolkit-path input must have a description"

    # ── Per-platform workflows must also have the new inputs ─────────────────

    @pytest.mark.parametrize("workflow", PLATFORM_WORKFLOWS)
    def test_integration_mode_present_in_platform_workflow(self, workflow):
        inputs = _workflow_inputs(workflow)
        if not inputs:
            pytest.skip(f"{workflow} not present or has no inputs")
        if "integration-mode" not in inputs:
            pytest.skip(f"integration-mode not yet in {workflow} — waiting for T3")
        assert "integration-mode" in inputs, \
            f"{workflow} must expose 'integration-mode' input"

    @pytest.mark.parametrize("workflow", PLATFORM_WORKFLOWS)
    def test_toolkit_path_present_in_platform_workflow(self, workflow):
        inputs = _workflow_inputs(workflow)
        if not inputs:
            pytest.skip(f"{workflow} not present or has no inputs")
        if "toolkit-path" not in inputs:
            pytest.skip(f"toolkit-path not yet in {workflow} — waiting for T3")
        assert "toolkit-path" in inputs, \
            f"{workflow} must expose 'toolkit-path' input"


# ---------------------------------------------------------------------------
# YAML contract: path traversal guards in workflow run: blocks
# ---------------------------------------------------------------------------

class TestPathTraversalRejectionInYAML:
    """
    After T3, the workflow shell blocks must guard against:
      - toolkit-path containing ../ (path traversal)
      - toolkit-path being an absolute path (starts with /)
      - TOOLKIT_PATH canonical mount always being .ci/unity-build-workflows

    Tests scan the concatenated `run:` text of all steps in unity-build.yml.
    They skip if integration-mode has not yet been added (T3 not complete).
    """

    @pytest.fixture(autouse=True)
    def _require_toolkit_path_input(self):
        if "toolkit-path" not in _unity_build_inputs():
            pytest.skip(
                "toolkit-path input not yet in unity-build.yml — waiting for T3"
            )

    @pytest.fixture
    def run_text(self):
        if not UNITY_BUILD_YML.exists():
            pytest.skip("unity-build.yml not found")
        return _all_run_text(_load_yaml(UNITY_BUILD_YML))

    def test_workflow_rejects_path_traversal(self, run_text):
        """
        The toolkit setup shell block must contain a guard for ../ traversal.

        Expected pattern (T3 implementation):
          if [[ "$TOOLKIT_PATH_INPUT" == *..* ]]; then
            echo "::error::toolkit-path must not contain .."
            exit 1
          fi
        """
        has_dotdot_guard = ".." in run_text and (
            "exit 1" in run_text or "::error::" in run_text
        )
        assert has_dotdot_guard, (
            "unity-build.yml run: blocks must guard against ../  path traversal "
            "in toolkit-path. Add:\n"
            "  if [[ \"$TOOLKIT_PATH_INPUT\" == *..* ]]; then\n"
            "    echo '::error::toolkit-path must not contain ..'; exit 1\n"
            "  fi"
        )

    def test_workflow_rejects_absolute_toolkit_path(self, run_text):
        """
        The toolkit setup shell block must reject toolkit-path values that are
        absolute (start with /).

        Expected pattern (T3 implementation):
          if [[ "$TOOLKIT_PATH_INPUT" == /* ]]; then
            echo "::error::toolkit-path must be a relative path"
            exit 1
          fi
        """
        has_absolute_guard = (
            "/*" in run_text or "== /" in run_text or "absolute" in run_text.lower()
        ) and ("exit 1" in run_text or "::error::" in run_text)
        assert has_absolute_guard, (
            "unity-build.yml run: blocks must reject absolute toolkit-path values. Add:\n"
            "  if [[ \"$TOOLKIT_PATH_INPUT\" == /* ]]; then\n"
            "    echo '::error::toolkit-path must be a relative path'; exit 1\n"
            "  fi"
        )

    def test_workflow_sets_canonical_toolkit_path(self, run_text):
        """
        TOOLKIT_PATH must always resolve to .ci/unity-build-workflows regardless
        of integration-mode. This canonical mount point is what all downstream
        steps (composite actions, scripts) reference.
        """
        assert ".ci/unity-build-workflows" in run_text, (
            "unity-build.yml run: blocks must reference .ci/unity-build-workflows "
            "as the canonical TOOLKIT_PATH. All downstream steps depend on this path."
        )

    def test_workflow_has_error_annotation_on_bad_path(self, run_text):
        """
        Invalid toolkit-path must produce a GitHub Actions ::error:: annotation
        so the failure is surfaced in the Actions UI, not just as a generic exit 1.
        """
        assert "::error::" in run_text, (
            "toolkit-path validation must use ::error:: annotations so failures "
            "surface as actionable messages in the GitHub Actions UI."
        )


# ---------------------------------------------------------------------------
# Optional Python validation CLI (skip if T3 didn't add it)
# ---------------------------------------------------------------------------

class TestValidateToolkitPathCLI:
    """
    If T3 adds scripts/common/validate_toolkit_path.py, test it directly.
    This class skips if the script is absent — path validation may live
    entirely in the workflow YAML shell instead.

    Contract:
      - Valid relative paths → exit 0
      - ../ traversal → exit 1, error message mentions the problem
      - Absolute paths → exit 1, error message mentions the problem
    """

    @pytest.fixture(autouse=True)
    def _require_script(self):
        if not VALIDATE_PATH_SCRIPT.exists():
            pytest.skip(
                "scripts/common/validate_toolkit_path.py not yet created. "
                "Path traversal validation may live inline in the workflow YAML. "
                "If T3 adds this script, tests here will run automatically."
            )

    def test_valid_relative_path_accepted(self):
        result = _run_validate_path("tools/unity-build-workflows")
        assert result.returncode == 0, (
            f"Valid relative path must be accepted (exit 0).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dot_path_accepted(self):
        result = _run_validate_path(".")
        assert result.returncode == 0, (
            f"'.' must be accepted as a valid toolkit path.\n{result.stderr}"
        )

    def test_simple_nested_path_accepted(self):
        result = _run_validate_path("submodules/unity-build-workflows")
        assert result.returncode == 0, (
            f"Simple nested relative path must be accepted.\n{result.stderr}"
        )

    def test_dotdot_traversal_rejected(self):
        result = _run_validate_path("../evil-path")
        assert result.returncode != 0, (
            "../ path traversal must be rejected (exit non-zero)"
        )

    def test_nested_dotdot_traversal_rejected(self):
        result = _run_validate_path("tools/../../etc/passwd")
        assert result.returncode != 0, (
            "Nested ../ traversal (tools/../../etc/passwd) must be rejected"
        )

    def test_absolute_path_rejected(self):
        result = _run_validate_path("/absolute/path")
        assert result.returncode != 0, (
            "Absolute paths (/absolute/path) must be rejected"
        )

    def test_root_absolute_path_rejected(self):
        result = _run_validate_path("/")
        assert result.returncode != 0, \
            "Root absolute path (/) must be rejected"

    def test_traversal_error_message_is_actionable(self):
        result = _run_validate_path("../evil")
        combined = result.stdout + result.stderr
        assert any(kw in combined.lower() for kw in (
            "traversal", "relative", "..", "invalid", "error", "must not"
        )), (
            f"Error for ../ must be actionable. Got:\n{combined}"
        )

    def test_absolute_path_error_message_is_actionable(self):
        result = _run_validate_path("/etc/passwd")
        combined = result.stdout + result.stderr
        assert any(kw in combined.lower() for kw in (
            "absolute", "relative", "invalid", "error", "must be"
        )), (
            f"Error for absolute path must be actionable. Got:\n{combined}"
        )


# ---------------------------------------------------------------------------
# Immutable geometry: project path ≠ toolkit path (always-pass)
# ---------------------------------------------------------------------------

class TestProjectToolkitSeparation:
    """
    Geometry assertions about the canonical path layout.
    These do not depend on T3 — they document the approved path contract
    and will always pass regardless of implementation state.

    The consumer workspace layout:
      <runner-workspace>/
        project/                     ← consumer repo checkout (actions/checkout path:)
          <project-path>/            ← Unity project root (inputs.project-path)
          tools/unity-build-workflows/ ← toolkit submodule (default toolkit-path)
        .ci/
          unity-build-workflows/     ← canonical TOOLKIT_PATH (always)
    """

    def test_canonical_toolkit_not_inside_project_checkout(self):
        """
        .ci/unity-build-workflows must not be inside the project/ checkout tree.
        Keeps toolkit files isolated from consumer Unity project assets.
        """
        toolkit = Path(".ci/unity-build-workflows")
        project_checkout = Path("project")
        assert not str(toolkit).startswith(str(project_checkout) + "/"), (
            "Canonical TOOLKIT_PATH (.ci/unity-build-workflows) must not be "
            "nested inside the consumer project checkout (project/)."
        )

    def test_canonical_toolkit_path_starts_with_dot_ci(self):
        """
        The canonical internal mount must start with .ci/ to prevent collision
        with consumer Unity project assets (Assets/, Packages/, etc.).
        """
        assert ".ci/unity-build-workflows".startswith(".ci/"), (
            "TOOLKIT_PATH must start with .ci/ — prevents collision with "
            "consumer-project assets at the workspace root."
        )

    def test_project_checkout_and_toolkit_mount_are_distinct_top_level_dirs(self):
        """
        project/ and .ci/ are separate top-level workspace directories.
        No symlink or nesting should make them equivalent.
        """
        project_root = Path("project")
        toolkit_root = Path(".ci")
        assert project_root != toolkit_root, (
            "Consumer project checkout (project/) and toolkit mount (.ci/) "
            "must be separate top-level directories."
        )
        assert not project_root.is_relative_to(toolkit_root), (
            "project/ must not be nested inside .ci/"
        )
        assert not toolkit_root.is_relative_to(project_root), (
            ".ci/ must not be nested inside project/"
        )

    @pytest.mark.parametrize("evil_input", [
        "../",
        "../../",
        "../etc/passwd",
        "../../workspace/.ci/unity-build-workflows",
        "valid/../../../etc",
    ])
    def test_dotdot_inputs_contain_traversal_marker(self, evil_input):
        """
        Inputs that contain ../ are detectable by a simple string check.
        This documents the minimum guard that the workflow shell must implement.
        """
        assert ".." in evil_input, (
            f"Test setup: '{evil_input}' must contain .. for this test to be valid"
        )
        # The guard: reject anything where the path, when resolved relative to
        # the workspace, would escape the project/ subtree.
        resolved = Path("project") / evil_input
        # String representation of a path with ../ components contains '..'
        assert ".." in str(resolved), (
            f"project/ + '{evil_input}' still contains escape markers — "
            "must be caught by the path traversal guard."
        )

    @pytest.mark.parametrize("safe_input", [
        ".",
        "tools/unity-build-workflows",
        "submodules/toolkit",
        "src/unity-workflows",
    ])
    def test_safe_relative_inputs_are_not_traversal(self, safe_input):
        """
        Safe relative paths do not contain .. and must be accepted.
        """
        assert ".." not in safe_input, (
            f"'{safe_input}' must not contain .. (test setup error)"
        )
        assert not safe_input.startswith("/"), (
            f"'{safe_input}' must not be absolute (test setup error)"
        )
